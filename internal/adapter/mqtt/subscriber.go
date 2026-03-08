package mqtt

import (
	"context"
	"fmt"
	"log/slog"
	"net/url"

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

// Start se connecte au broker MQTT et écoute les messages jusqu'à
// ce que le context soit annulé (ex: SIGTERM, arrêt de l'addon).
// Cette méthode est BLOQUANTE : elle ne retourne que quand ctx est annulé.
func (s *Subscriber) Start(ctx context.Context) error {
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

			// On s'abonne au topic dès qu'on est connecté
			_, subErr := cm.Subscribe(ctx, &paho.Subscribe{
				Subscriptions: []paho.SubscribeOptions{
					{Topic: s.topic, QoS: 1},
				},
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
					s.logger.Debug("message MQTT reçu", "topic", pr.Packet.Topic, "size", len(pr.Packet.Payload), "payload", pr.Packet.Payload)

					if handleErr := s.handler.Handle(pr.Packet.Payload); handleErr != nil {
						s.logger.Error("erreur traitement message", "error", handleErr)
					}
					// On retourne true = message traité (ack au broker)
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

	// On attend que la première connexion s'établisse
	if err = cm.AwaitConnection(ctx); err != nil {
		return fmt.Errorf("impossible de se connecter au broker: %w", err)
	}

	// On bloque ici jusqu'à ce que le context soit annulé (arrêt de l'addon)
	<-ctx.Done()
	s.logger.Info("arrêt du subscriber MQTT")
	return nil
}
