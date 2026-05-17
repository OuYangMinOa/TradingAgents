package news

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/mmcdole/gofeed"
	"github.com/tradingagents-tw/datacollector/internal/models"
)

// rssSource defines an RSS feed source.
type rssSource struct {
	Name string
	URL  string
}

var sources = []rssSource{
	{Name: "經濟日報", URL: "https://money.udn.com/rssfeed/news/1/5591"},
	{Name: "工商時報", URL: "https://ctee.com.tw/feed"},
	// MoneyDJ 無 RSS，需額外實作 HTML scraper (TODO Phase 2)
}

type Crawler struct {
	parser *gofeed.Parser
}

func NewCrawler() *Crawler {
	fp := gofeed.NewParser()
	fp.Client = &http.Client{Timeout: 20 * time.Second}
	return &Crawler{parser: fp}
}

// FetchAll fetches all configured RSS sources and returns deduplicated articles.
func (c *Crawler) FetchAll(ctx context.Context) ([]models.NewsArticle, error) {
	var all []models.NewsArticle
	seen := make(map[string]struct{})

	for _, src := range sources {
		articles, err := c.fetchSource(ctx, src)
		if err != nil {
			log.Printf("news: skip source %s: %v", src.Name, err)
			continue
		}
		for _, a := range articles {
			if _, ok := seen[a.URL]; ok {
				continue
			}
			seen[a.URL] = struct{}{}
			all = append(all, a)
		}
	}

	if len(all) == 0 {
		return nil, fmt.Errorf("all news sources failed")
	}
	return all, nil
}

func (c *Crawler) fetchSource(ctx context.Context, src rssSource) ([]models.NewsArticle, error) {
	feed, err := c.parser.ParseURLWithContext(src.URL, ctx)
	if err != nil {
		return nil, fmt.Errorf("parse RSS %s: %w", src.URL, err)
	}

	out := make([]models.NewsArticle, 0, len(feed.Items))
	for _, item := range feed.Items {
		if item.Link == "" {
			continue
		}
		publishedAt := time.Now()
		if item.PublishedParsed != nil {
			publishedAt = *item.PublishedParsed
		}

		out = append(out, models.NewsArticle{
			Source:      src.Name,
			Title:       item.Title,
			Summary:     item.Description,
			URL:         item.Link,
			PublishedAt: publishedAt,
		})
	}
	return out, nil
}
