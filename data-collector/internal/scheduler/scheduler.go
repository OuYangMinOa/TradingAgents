package scheduler

import (
	"context"
	"log"
	"time"

	"github.com/robfig/cron/v3"
	"github.com/tradingagents-tw/datacollector/internal/config"
	"github.com/tradingagents-tw/datacollector/internal/db"
	"github.com/tradingagents-tw/datacollector/internal/finmind"
	"github.com/tradingagents-tw/datacollector/internal/news"
	"github.com/tradingagents-tw/datacollector/internal/ptt"
	redispub "github.com/tradingagents-tw/datacollector/internal/redis"
)

type Scheduler struct {
	cron      *cron.Cron
	db        *db.DB
	finmind   *finmind.Client
	pttCrawler *ptt.Crawler
	newsCrawler *news.Crawler
	publisher *redispub.Publisher
	cfg       *config.Config
}

func New(database *db.DB, fm *finmind.Client, pub *redispub.Publisher, cfg *config.Config) *Scheduler {
	c := cron.New(cron.WithLocation(time.FixedZone("Asia/Taipei", 8*60*60)))
	s := &Scheduler{
		cron:        c,
		db:          database,
		finmind:     fm,
		pttCrawler:  ptt.NewCrawler(),
		newsCrawler: news.NewCrawler(),
		publisher:   pub,
		cfg:         cfg,
	}

	// 每個交易日 15:30 拉取股價 + 法人資料，完成後通知 Python
	c.AddFunc("30 15 * * 1-5", func() { s.runDailyCollection() })

	// 每小時爬取 PTT
	c.AddFunc("0 * * * *", func() { s.runPTTCrawl() })

	// 每 2 小時爬取新聞
	c.AddFunc("0 */2 * * *", func() { s.runNewsCrawl() })

	return s
}

func (s *Scheduler) Start() {
	log.Println("scheduler: starting")
	s.cron.Start()
}

func (s *Scheduler) Stop() {
	log.Println("scheduler: stopping")
	ctx := s.cron.Stop()
	<-ctx.Done()
}

// RunNow immediately executes all collection jobs (for testing / manual trigger).
func (s *Scheduler) RunNow() {
	s.runDailyCollection()
	s.runPTTCrawl()
	s.runNewsCrawl()
}

func (s *Scheduler) runDailyCollection() {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()

	today := time.Now().Format("2006-01-02")
	log.Printf("scheduler: daily collection start for %s", today)

	for _, stockID := range s.cfg.WatchList {
		// Stock prices
		prices, err := s.finmind.FetchStockPrices(ctx, stockID, today)
		if err != nil {
			log.Printf("finmind: fetch prices %s: %v", stockID, err)
		} else if err := s.db.UpsertStockPrices(ctx, prices); err != nil {
			log.Printf("db: upsert prices %s: %v", stockID, err)
		} else {
			log.Printf("finmind: saved %d price rows for %s", len(prices), stockID)
		}

		// Institutional investors
		institutional, err := s.finmind.FetchInstitutional(ctx, stockID, today)
		if err != nil {
			log.Printf("finmind: fetch institutional %s: %v", stockID, err)
		} else if err := s.db.UpsertInstitutional(ctx, institutional); err != nil {
			log.Printf("db: upsert institutional %s: %v", stockID, err)
		} else {
			log.Printf("finmind: saved %d institutional rows for %s", len(institutional), stockID)
		}
	}

	// Notify Python orchestrator
	if err := s.publisher.PublishDataReady(ctx, today, s.cfg.WatchList); err != nil {
		log.Printf("redis: publish failed: %v", err)
	}

	log.Printf("scheduler: daily collection done for %s", today)
}

func (s *Scheduler) runPTTCrawl() {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	log.Println("scheduler: ptt crawl start")
	posts, err := s.pttCrawler.FetchLatest(ctx, 50)
	if err != nil {
		log.Printf("ptt: fetch failed: %v", err)
		return
	}

	if err := s.db.UpsertPTTPosts(ctx, posts); err != nil {
		log.Printf("db: upsert ptt posts: %v", err)
		return
	}
	log.Printf("scheduler: ptt crawl done, saved %d posts", len(posts))
}

func (s *Scheduler) runNewsCrawl() {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	log.Println("scheduler: news crawl start")
	articles, err := s.newsCrawler.FetchAll(ctx)
	if err != nil {
		log.Printf("news: fetch failed: %v", err)
		return
	}

	if err := s.db.UpsertNewsArticles(ctx, articles); err != nil {
		log.Printf("db: upsert news: %v", err)
		return
	}
	log.Printf("scheduler: news crawl done, saved %d articles", len(articles))
}
