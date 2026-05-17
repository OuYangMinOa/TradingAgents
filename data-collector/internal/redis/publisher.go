package redispub

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

const channelDataReady = "tradingagents:data_ready"

type Publisher struct {
	client *redis.Client
}

type DataReadyEvent struct {
	Date      string    `json:"date"`
	Stocks    []string  `json:"stocks"`
	Timestamp time.Time `json:"timestamp"`
}

func NewPublisher(redisURL string) (*Publisher, error) {
	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, fmt.Errorf("parse redis URL: %w", err)
	}
	client := redis.NewClient(opt)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("redis ping: %w", err)
	}

	log.Println("redis: connected")
	return &Publisher{client: client}, nil
}

func (p *Publisher) Close() error { return p.client.Close() }

// PublishDataReady signals the Python orchestrator that data collection is done.
func (p *Publisher) PublishDataReady(ctx context.Context, date string, stocks []string) error {
	event := DataReadyEvent{
		Date:      date,
		Stocks:    stocks,
		Timestamp: time.Now(),
	}
	payload, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal event: %w", err)
	}

	if err := p.client.Publish(ctx, channelDataReady, payload).Err(); err != nil {
		return fmt.Errorf("redis publish: %w", err)
	}

	log.Printf("redis: published data_ready for %s (%d stocks)", date, len(stocks))
	return nil
}
