package models

import "time"

type StockPrice struct {
	StockID string
	Date    time.Time
	Open    float64
	High    float64
	Low     float64
	Close   float64
	Volume  int64
}

// InstitutionalRow represents one institution's buy/sell for a stock on a date.
// FinMind returns one row per institution type; we aggregate into InstitutionalDay.
type InstitutionalRow struct {
	StockID string
	Date    time.Time
	Name    string // 外資 | 投信 | 自營商
	Buy     int64
	Sell    int64
}

type InstitutionalDay struct {
	StockID     string
	Date        time.Time
	ForeignBuy  int64
	ForeignSell int64
	TrustBuy    int64
	TrustSell   int64
	DealerBuy   int64
	DealerSell  int64
}

type PTTPost struct {
	ArticleID string
	Title     string
	Author    string
	PushCount int
	BooCount  int
	PostedAt  time.Time
}

type NewsArticle struct {
	Source      string
	Title       string
	Summary     string
	URL         string
	PublishedAt time.Time
}
