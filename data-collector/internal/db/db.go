package db

import (
	"context"
	"fmt"
	"log"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/tradingagents-tw/datacollector/internal/models"
)

type DB struct {
	pool *pgxpool.Pool
}

func New(ctx context.Context, dsn string) (*DB, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, fmt.Errorf("connect db: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("ping db: %w", err)
	}
	log.Println("db: connected")
	return &DB{pool: pool}, nil
}

func (d *DB) Close() { d.pool.Close() }

func (d *DB) UpsertStockPrices(ctx context.Context, prices []models.StockPrice) error {
	for _, p := range prices {
		_, err := d.pool.Exec(ctx, `
			INSERT INTO stock_daily (stock_id, date, open, high, low, close, volume)
			VALUES ($1, $2, $3, $4, $5, $6, $7)
			ON CONFLICT (stock_id, date) DO UPDATE SET
				open   = EXCLUDED.open,
				high   = EXCLUDED.high,
				low    = EXCLUDED.low,
				close  = EXCLUDED.close,
				volume = EXCLUDED.volume`,
			p.StockID, p.Date, p.Open, p.High, p.Low, p.Close, p.Volume,
		)
		if err != nil {
			return fmt.Errorf("upsert stock_daily %s %s: %w", p.StockID, p.Date.Format("2006-01-02"), err)
		}
	}
	return nil
}

func (d *DB) UpsertInstitutional(ctx context.Context, days []models.InstitutionalDay) error {
	for _, day := range days {
		_, err := d.pool.Exec(ctx, `
			INSERT INTO institutional_investors
				(stock_id, date, foreign_buy, foreign_sell, trust_buy, trust_sell, dealer_buy, dealer_sell)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
			ON CONFLICT (stock_id, date) DO UPDATE SET
				foreign_buy  = EXCLUDED.foreign_buy,
				foreign_sell = EXCLUDED.foreign_sell,
				trust_buy    = EXCLUDED.trust_buy,
				trust_sell   = EXCLUDED.trust_sell,
				dealer_buy   = EXCLUDED.dealer_buy,
				dealer_sell  = EXCLUDED.dealer_sell`,
			day.StockID, day.Date,
			day.ForeignBuy, day.ForeignSell,
			day.TrustBuy, day.TrustSell,
			day.DealerBuy, day.DealerSell,
		)
		if err != nil {
			return fmt.Errorf("upsert institutional %s %s: %w", day.StockID, day.Date.Format("2006-01-02"), err)
		}
	}
	return nil
}

func (d *DB) UpsertPTTPosts(ctx context.Context, posts []models.PTTPost) error {
	for _, p := range posts {
		_, err := d.pool.Exec(ctx, `
			INSERT INTO ptt_posts (article_id, title, author, push_count, boo_count, posted_at)
			VALUES ($1,$2,$3,$4,$5,$6)
			ON CONFLICT (article_id) DO NOTHING`,
			p.ArticleID, p.Title, p.Author, p.PushCount, p.BooCount, p.PostedAt,
		)
		if err != nil {
			return fmt.Errorf("upsert ptt_post %s: %w", p.ArticleID, err)
		}
	}
	return nil
}

func (d *DB) UpsertNewsArticles(ctx context.Context, articles []models.NewsArticle) error {
	for _, a := range articles {
		_, err := d.pool.Exec(ctx, `
			INSERT INTO news_articles (source, title, summary, url, published_at)
			VALUES ($1,$2,$3,$4,$5)
			ON CONFLICT (url) DO NOTHING`,
			a.Source, a.Title, a.Summary, a.URL, a.PublishedAt,
		)
		if err != nil {
			return fmt.Errorf("upsert news %s: %w", a.URL, err)
		}
	}
	return nil
}

// --- inspect queries ---

type TableCount struct {
	Table string
	Rows  int64
}

func (d *DB) QueryTableCounts(ctx context.Context) ([]TableCount, error) {
	tables := []string{"stock_daily", "institutional_investors", "news_articles", "ptt_posts"}
	out := make([]TableCount, 0, len(tables))
	for _, t := range tables {
		var n int64
		err := d.pool.QueryRow(ctx, "SELECT COUNT(*) FROM "+t).Scan(&n)
		if err != nil {
			return nil, fmt.Errorf("count %s: %w", t, err)
		}
		out = append(out, TableCount{Table: t, Rows: n})
	}
	return out, nil
}

func (d *DB) QueryLatestPrices(ctx context.Context) ([]models.StockPrice, error) {
	rows, err := d.pool.Query(ctx, `
		SELECT DISTINCT ON (stock_id) stock_id, date, open, high, low, close, volume
		FROM stock_daily
		ORDER BY stock_id, date DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []models.StockPrice
	for rows.Next() {
		var p models.StockPrice
		if err := rows.Scan(&p.StockID, &p.Date, &p.Open, &p.High, &p.Low, &p.Close, &p.Volume); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func (d *DB) QueryLatestInstitutional(ctx context.Context) ([]models.InstitutionalDay, error) {
	rows, err := d.pool.Query(ctx, `
		SELECT DISTINCT ON (stock_id)
			stock_id, date, foreign_buy, foreign_sell, trust_buy, trust_sell, dealer_buy, dealer_sell
		FROM institutional_investors
		ORDER BY stock_id, date DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []models.InstitutionalDay
	for rows.Next() {
		var d models.InstitutionalDay
		if err := rows.Scan(&d.StockID, &d.Date,
			&d.ForeignBuy, &d.ForeignSell,
			&d.TrustBuy, &d.TrustSell,
			&d.DealerBuy, &d.DealerSell); err != nil {
			return nil, err
		}
		out = append(out, d)
	}
	return out, rows.Err()
}

func (d *DB) QueryLatestNews(ctx context.Context, limit int) ([]models.NewsArticle, error) {
	rows, err := d.pool.Query(ctx, `
		SELECT source, title, url, published_at
		FROM news_articles
		ORDER BY published_at DESC
		LIMIT $1`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []models.NewsArticle
	for rows.Next() {
		var a models.NewsArticle
		if err := rows.Scan(&a.Source, &a.Title, &a.URL, &a.PublishedAt); err != nil {
			return nil, err
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

func (d *DB) QueryLatestPTTPosts(ctx context.Context, limit int) ([]models.PTTPost, error) {
	rows, err := d.pool.Query(ctx, `
		SELECT article_id, title, author, push_count, boo_count, posted_at
		FROM ptt_posts
		ORDER BY posted_at DESC
		LIMIT $1`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []models.PTTPost
	for rows.Next() {
		var p models.PTTPost
		if err := rows.Scan(&p.ArticleID, &p.Title, &p.Author, &p.PushCount, &p.BooCount, &p.PostedAt); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}
