package main

import (
	"context"
	"flag"
	"fmt"
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
	inspect := flag.Bool("inspect", false, "print latest collected data from DB then exit")
	flag.Parse()

	cfg := config.Default

	ctx := context.Background()

	database, err := db.New(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("db init: %v", err)
	}
	defer database.Close()

	if *inspect {
		runInspect(ctx, database)
		return
	}

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

func runInspect(ctx context.Context, database *db.DB) {
	// Table row counts
	counts, err := database.QueryTableCounts(ctx)
	if err != nil {
		log.Fatalf("inspect: %v", err)
	}
	fmt.Println("=== Table Counts ===")
	for _, c := range counts {
		fmt.Printf("  %-28s %d rows\n", c.Table, c.Rows)
	}

	// Latest price per stock
	fmt.Println("\n=== Latest Stock Prices ===")
	fmt.Printf("  %-6s  %-10s  %7s  %7s  %7s  %7s  %12s\n",
		"STOCK", "DATE", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME")
	prices, err := database.QueryLatestPrices(ctx)
	if err != nil {
		fmt.Printf("  error: %v\n", err)
	} else if len(prices) == 0 {
		fmt.Println("  (no data)")
	} else {
		for _, p := range prices {
			fmt.Printf("  %-6s  %-10s  %7.2f  %7.2f  %7.2f  %7.2f  %12d\n",
				p.StockID, p.Date.Format("2006-01-02"),
				p.Open, p.High, p.Low, p.Close, p.Volume)
		}
	}

	// Latest institutional per stock
	fmt.Println("\n=== Latest Institutional Investors ===")
	fmt.Printf("  %-6s  %-10s  %10s  %10s  %10s  %10s\n",
		"STOCK", "DATE", "FOR.BUY", "FOR.SELL", "TRUST.BUY", "TRUST.SELL")
	inst, err := database.QueryLatestInstitutional(ctx)
	if err != nil {
		fmt.Printf("  error: %v\n", err)
	} else if len(inst) == 0 {
		fmt.Println("  (no data)")
	} else {
		for _, d := range inst {
			fmt.Printf("  %-6s  %-10s  %10d  %10d  %10d  %10d\n",
				d.StockID, d.Date.Format("2006-01-02"),
				d.ForeignBuy, d.ForeignSell, d.TrustBuy, d.TrustSell)
		}
	}

	// Latest 10 news articles
	fmt.Println("\n=== Latest News (10) ===")
	fmt.Printf("  %-10s  %-19s  %s\n", "SOURCE", "PUBLISHED", "TITLE")
	articles, err := database.QueryLatestNews(ctx, 10)
	if err != nil {
		fmt.Printf("  error: %v\n", err)
	} else if len(articles) == 0 {
		fmt.Println("  (no data)")
	} else {
		for _, a := range articles {
			title := a.Title
			if len(title) > 50 {
				title = title[:47] + "..."
			}
			fmt.Printf("  %-10s  %-19s  %s\n",
				a.Source, a.PublishedAt.Format("2006-01-02 15:04"), title)
		}
	}

	// Latest 10 PTT posts
	fmt.Println("\n=== Latest PTT Posts (10) ===")
	fmt.Printf("  %4s  %4s  %-12s  %s\n", "PUSH", "BOO", "AUTHOR", "TITLE")
	posts, err := database.QueryLatestPTTPosts(ctx, 10)
	if err != nil {
		fmt.Printf("  error: %v\n", err)
	} else if len(posts) == 0 {
		fmt.Println("  (no data)")
	} else {
		for _, p := range posts {
			title := p.Title
			if len(title) > 50 {
				title = title[:47] + "..."
			}
			fmt.Printf("  %4d  %4d  %-12s  %s\n",
				p.PushCount, p.BooCount, p.Author, title)
		}
	}
}
