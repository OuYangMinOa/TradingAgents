package ptt

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/tradingagents-tw/datacollector/internal/models"
)

const (
	indexURL  = "https://www.ptt.cc/bbs/Stock/index.json"
	articleFmt = "https://www.ptt.cc/bbs/Stock/%s.json"
	// Filter out posts with boo_count below threshold (likely spam/ads)
	minBooThreshold = -10
)

type Crawler struct {
	client *http.Client
}

func NewCrawler() *Crawler {
	return &Crawler{
		client: &http.Client{Timeout: 15 * time.Second},
	}
}

func (c *Crawler) get(ctx context.Context, u string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return nil, err
	}
	// PTT requires over18 cookie
	req.AddCookie(&http.Cookie{Name: "over18", Value: "1"})

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d for %s", resp.StatusCode, u)
	}
	return io.ReadAll(resp.Body)
}

type indexResponse struct {
	Items []struct {
		ID string `json:"id"` // article filename without .json
	} `json:"items"`
}

type articleResponse struct {
	ID       string `json:"id"`
	Title    string `json:"title"`
	Author   string `json:"author"`
	Date     string `json:"date"` // e.g. "Sat Jan  6 12:34:56 2024"
	Comments []struct {
		Type    string `json:"push_tag"` // 推 | 噓 | →
		Content string `json:"push_content"`
	} `json:"push_list"`
}

// FetchLatest crawls the index page and fetches up to limit recent articles.
func (c *Crawler) FetchLatest(ctx context.Context, limit int) ([]models.PTTPost, error) {
	indexData, err := c.get(ctx, indexURL)
	if err != nil {
		return nil, fmt.Errorf("ptt index: %w", err)
	}

	var idx indexResponse
	if err := json.Unmarshal(indexData, &idx); err != nil {
		return nil, fmt.Errorf("parse ptt index: %w", err)
	}

	// Take up to `limit` most recent items
	items := idx.Items
	if len(items) > limit {
		items = items[len(items)-limit:]
	}

	var posts []models.PTTPost
	for _, item := range items {
		artData, err := c.get(ctx, fmt.Sprintf(articleFmt, item.ID))
		if err != nil {
			// Skip individual article errors to avoid blocking the whole crawl
			continue
		}

		var art articleResponse
		if err := json.Unmarshal(artData, &art); err != nil {
			continue
		}

		pushCount, booCount := countVotes(art.Comments)
		if booCount < minBooThreshold {
			continue // likely spam
		}

		postedAt := parsePTTDate(art.Date)

		posts = append(posts, models.PTTPost{
			ArticleID: art.ID,
			Title:     art.Title,
			Author:    strings.TrimSpace(art.Author),
			PushCount: pushCount,
			BooCount:  booCount,
			PostedAt:  postedAt,
		})
	}
	return posts, nil
}

func countVotes(comments []struct {
	Type    string `json:"push_tag"`
	Content string `json:"push_content"`
}) (push, boo int) {
	for _, c := range comments {
		switch strings.TrimSpace(c.Type) {
		case "推":
			push++
		case "噓":
			boo--
		}
	}
	return
}

// parsePTTDate parses PTT date format: "Sat Jan  6 12:34:56 2024"
func parsePTTDate(s string) time.Time {
	s = strings.Join(strings.Fields(s), " ")
	if t, err := time.Parse("Mon Jan 2 15:04:05 2006", s); err == nil {
		return t
	}
	// Fallback: try epoch string
	if epoch, err := strconv.ParseInt(s, 10, 64); err == nil {
		return time.Unix(epoch, 0)
	}
	return time.Now()
}
