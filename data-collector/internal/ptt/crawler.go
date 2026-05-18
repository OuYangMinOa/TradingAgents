package ptt

import (
	"bytes"
	"context"
	"crypto/tls"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/tradingagents-tw/datacollector/internal/models"
)

const (
	boardURL  = "https://www.ptt.cc/bbs/Stock/index.html"
	userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

type Crawler struct {
	client *http.Client
}

func NewCrawler() *Crawler {
	// PTT server RSTs when Go advertises h2 in ALPN; force HTTP/1.1 only.
	transport := &http.Transport{
		TLSClientConfig: &tls.Config{
			NextProtos: []string{"http/1.1"},
		},
	}
	return &Crawler{
		client: &http.Client{
			Timeout:   15 * time.Second,
			Transport: transport,
		},
	}
}

func (c *Crawler) get(ctx context.Context, u string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
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

// FetchLatest scrapes the PTT Stock board index and returns up to limit posts.
func (c *Crawler) FetchLatest(ctx context.Context, limit int) ([]models.PTTPost, error) {
	body, err := c.get(ctx, boardURL)
	if err != nil {
		return nil, fmt.Errorf("ptt board: %w", err)
	}

	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("parse ptt html: %w", err)
	}

	var posts []models.PTTPost
	doc.Find("div.r-ent").Each(func(_ int, s *goquery.Selection) {
		titleSel := s.Find(".title a")
		title := strings.TrimSpace(titleSel.Text())
		href, exists := titleSel.Attr("href")
		if !exists || title == "" {
			return // deleted post
		}

		// /bbs/Stock/M.1234567890.A.ABC.html → M.1234567890.A.ABC
		parts := strings.Split(href, "/")
		articleID := strings.TrimSuffix(parts[len(parts)-1], ".html")

		author := strings.TrimSpace(s.Find(".meta .author").Text())
		dateStr := strings.TrimSpace(s.Find(".meta .date").Text())
		pushCount, booCount := parseNrec(strings.TrimSpace(s.Find(".nrec").Text()))

		posts = append(posts, models.PTTPost{
			ArticleID: articleID,
			Title:     title,
			Author:    author,
			PushCount: pushCount,
			BooCount:  booCount,
			PostedAt:  parseBoardDate(dateStr),
		})
	})

	if len(posts) > limit {
		posts = posts[len(posts)-limit:]
	}
	return posts, nil
}

// parseNrec converts the board listing push summary to push/boo counts.
// "爆" = 100+ pushes, "XX"/"X" = heavy booes, number = net count.
func parseNrec(s string) (push, boo int) {
	switch s {
	case "爆":
		return 100, 0
	case "XX", "X":
		return 0, -100
	default:
		n, _ := strconv.Atoi(s)
		if n >= 0 {
			return n, 0
		}
		return 0, n
	}
}

// parseBoardDate parses the short date shown in the PTT board listing (e.g. " 5/17").
func parseBoardDate(s string) time.Time {
	s = strings.TrimSpace(s)
	parts := strings.Split(s, "/")
	if len(parts) != 2 {
		return time.Now()
	}
	month, err1 := strconv.Atoi(parts[0])
	day, err2 := strconv.Atoi(parts[1])
	if err1 != nil || err2 != nil {
		return time.Now()
	}
	now := time.Now()
	t := time.Date(now.Year(), time.Month(month), day, 0, 0, 0, 0, now.Location())
	// Roll back a year if date is in the future (e.g., Dec post seen in Jan)
	if t.After(now) {
		t = t.AddDate(-1, 0, 0)
	}
	return t
}
