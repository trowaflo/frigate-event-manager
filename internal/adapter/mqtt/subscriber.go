package mqtt

import (
	"context"
	"fmt"
	"log/slog"
	"net/url"
	"strings"

	"github.com/eclipse/paho.golang/autopaho"
	"github.com/eclipse/paho.golang/paho"
)

// Subscriber est l'adapter MQTT. Il se connecte au broker Frigate,
// s'abonne au topic des reviews, et transmet chaque message au MessageHandler.
//
// C'est la couche la plus "extérieure" de l'oignon :
// il connaît le réseau, TCP, MQTT... mais ne connaît PAS la logique métier.
type Subscriber struct {
	brokerURL string // ex: "tcp://192.168.1.50:1883"
	topic     string // ex: "frigate/reviews"
	clientID  string // identifiant unique de notre addon
	username  string
	password  string
	handler   *MessageHandler // à qui transmettre les messages
	logger    *slog.Logger

	// commandHandler est appelé pour les messages de commande (ex: switch notifications).
	// Peut être nil si pas de commande à gérer.
	commandHandler CommandHandler

	// cm est le ConnectionManager exposé pour permettre la publication MQTT.
	cm *autopaho.ConnectionManager
}

// CommandHandler traite les messages de commande reçus sur les topics de contrôle.
type CommandHandler interface {
	HandleCommand(topic string, payload []byte)
}

// NewSubscriber crée un subscriber MQTT.
//   - brokerURL : adresse du broker (ex: "tcp://localhost:1883")
//   - topic : topic Frigate à écouter (ex: "frigate/reviews")
//   - clientID : identifiant unique du client MQTT
//   - handler : le MessageHandler qui parsera les messages
func NewSubscriber(brokerURL, topic, clientID, username, password string, handler *MessageHandler, logger *slog.Logger) *Subscriber {
	return &Subscriber{
		brokerURL: brokerURL,
		topic:     topic,
		clientID:  clientID,
		username:  username,
		password:  password,
		handler:   handler,
		logger:    logger,
	}
}

// SetCommandHandler configure un handler pour les messages de commande MQTT.
func (s *Subscriber) SetCommandHandler(h CommandHandler) {
	s.commandHandler = h
}

// ConnectionManager retourne le ConnectionManager MQTT pour publier des messages.
// Retourne nil si Start() n'a pas encore été appelé.
func (s *Subscriber) ConnectionManager() *autopaho.ConnectionManager {
	return s.cm
}

// Start se connecte au broker MQTT et écoute les messages jusqu'à
// ce que le context soit annulé (ex: SIGTERM, arrêt de l'addon).
// Cette méthode est BLOQUANTE : elle ne retourne que quand ctx est annulé.
func (s *Subscriber) Start(ctx context.Context) error {
	if err := s.Connect(ctx); err != nil {
		return err
	}
	return s.Wait(ctx)
}

// Connect établit la connexion MQTT et attend la première connexion.
// Non-bloquant : retourne dès que la connexion est établie.
// Utilisez ConnectionManager() après Connect() pour publier.
func (s *Subscriber) Connect(ctx context.Context) error {
	serverURL, err := url.Parse(s.brokerURL)
	if err != nil {
		return fmt.Errorf("URL broker invalide %q: %w", s.brokerURL, err)
	}

	cliCfg := autopaho.ClientConfig{
		BrokerUrls:      []*url.URL{serverURL},
		KeepAlive:       30,
		ConnectUsername: s.username,
		ConnectPassword: []byte(s.password),
		OnConnectionUp: func(cm *autopaho.ConnectionManager, connAck *paho.Connack) {
			s.logger.Info("connecté au broker MQTT", "broker", s.brokerURL)

			// Subscriptions : topic principal + topic de commande (si configuré)
			subs := []paho.SubscribeOptions{
				{Topic: s.topic, QoS: 1},
			}
			if s.commandHandler != nil {
				commandTopic := "fem/fem/+/notifications/set"
				subs = append(subs, paho.SubscribeOptions{Topic: commandTopic, QoS: 1})
				s.logger.Info("abonnement commandes MQTT", "topic", commandTopic)
			}

			_, subErr := cm.Subscribe(ctx, &paho.Subscribe{
				Subscriptions: subs,
			})
			if subErr != nil {
				s.logger.Error("échec abonnement MQTT", "topic", s.topic, "error", subErr)
				return
			}
			s.logger.Info("abonné au topic", "topic", s.topic)
		},
		OnConnectError: func(err error) {
			s.logger.Error("erreur connexion MQTT", "error", err)
		},
		ClientConfig: paho.ClientConfig{
			ClientID: s.clientID,
			OnPublishReceived: []func(paho.PublishReceived) (bool, error){
				func(pr paho.PublishReceived) (bool, error) {
					topic := pr.Packet.Topic

					// Router : commandes vs événements
					if s.commandHandler != nil && strings.HasSuffix(topic, "/set") {
						s.logger.Debug("commande MQTT reçue", "topic", topic, "payload", string(pr.Packet.Payload))
						s.commandHandler.HandleCommand(topic, pr.Packet.Payload)
						return true, nil
					}

					s.logger.Debug("message MQTT reçu", "topic", topic, "size", len(pr.Packet.Payload), "payload", pr.Packet.Payload)

					if handleErr := s.handler.Handle(pr.Packet.Payload); handleErr != nil {
						s.logger.Error("erreur traitement message", "error", handleErr)
					}
					return true, nil
				},
			},
		},
	}

	// AutoPaho gère la reconnexion automatique si le broker redémarre
	cm, err := autopaho.NewConnection(ctx, cliCfg)
	if err != nil {
		return fmt.Errorf("impossible de créer la connexion MQTT: %w", err)
	}
	s.cm = cm

	// On attend que la première connexion s'établisse
	if err = cm.AwaitConnection(ctx); err != nil {
		return fmt.Errorf("impossible de se connecter au broker: %w", err)
	}
	return nil
}

// Wait bloque jusqu'à ce que le context soit annulé (arrêt de l'addon).
func (s *Subscriber) Wait(ctx context.Context) error {
	<-ctx.Done()
	s.logger.Info("arrêt du subscriber MQTT")
	return nil
}
