package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/tradingagents-tw/datacollector/internal/config"
	"github.com/tradingagents-tw/datacollector/internal/db"
	"github.com/tradingagents-tw/datacollector/internal/finmind"
	redispub "github.com/tradingagents-tw/datacollector/internal/redis"
	"github.com/tradingagents-tw/datacollector/internal/scheduler"
)

func main() {
	runNow := flag.Bool("run-now", false, "immediately run all collection jobs then exit")
	flag.Parse()

	cfg := config.Default

	ctx := context.Background()

	database, err := db.New(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("db init: %v", err)
	}
	defer database.Close()

	publisher, err := redispub.NewPublisher(cfg.RedisURL)
	if err != nil {
		log.Fatalf("redis init: %v", err)
	}
	defer publisher.Close()

	fm := finmind.NewClient(cfg.FinMindToken)
	sched := scheduler.New(database, fm, publisher, cfg)

	if *runNow {
		log.Println("main: running all jobs immediately")
		sched.RunNow()
		log.Println("main: done")
		return
	}

	sched.Start()
	log.Println("main: scheduler running, press Ctrl+C to stop")

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
	<-quit

	sched.Stop()
	log.Println("main: shutdown complete")
}
