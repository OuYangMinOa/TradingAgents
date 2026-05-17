package finmind

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/tradingagents-tw/datacollector/internal/models"
)

const baseURL = "https://api.finmindtrade.com/api/v4/data"

type Client struct {
	token      string
	httpClient *http.Client
}

func NewClient(token string) *Client {
	return &Client{
		token: token,
		httpClient: &http.Client{Timeout: 30 * time.Second},
	}
}

type finmindResponse struct {
	Msg    string          `json:"msg"`
	Status int             `json:"status"`
	Data   json.RawMessage `json:"data"`
}

// get fetches FinMind API with retry (max 3, exponential backoff).
func (c *Client) get(ctx context.Context, params url.Values) (json.RawMessage, error) {
	params.Set("token", c.token)
	reqURL := baseURL + "?" + params.Encode()

	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(time.Duration(attempt*attempt) * time.Second):
			}
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
		if err != nil {
			return nil, err
		}

		resp, err := c.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("attempt %d: %w", attempt+1, err)
			continue
		}

		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			lastErr = fmt.Errorf("read body attempt %d: %w", attempt+1, err)
			continue
		}

		if resp.StatusCode != http.StatusOK {
			lastErr = fmt.Errorf("attempt %d: HTTP %d", attempt+1, resp.StatusCode)
			continue
		}

		var fin finmindResponse
		if err := json.Unmarshal(body, &fin); err != nil {
			lastErr = fmt.Errorf("parse response: %w", err)
			continue
		}
		if fin.Status != 200 {
			lastErr = fmt.Errorf("finmind error: %s", fin.Msg)
			continue
		}

		return fin.Data, nil
	}
	return nil, fmt.Errorf("all retries failed: %w", lastErr)
}

// FetchStockPrices fetches TaiwanStockPrice for a single stock from startDate.
func (c *Client) FetchStockPrices(ctx context.Context, stockID, startDate string) ([]models.StockPrice, error) {
	params := url.Values{
		"dataset":    {"TaiwanStockPrice"},
		"data_id":    {stockID},
		"start_date": {startDate},
	}

	data, err := c.get(ctx, params)
	if err != nil {
		return nil, fmt.Errorf("FetchStockPrices %s: %w", stockID, err)
	}

	type row struct {
		Date   string  `json:"date"`
		Open   float64 `json:"open"`
		Max    float64 `json:"max"`
		Min    float64 `json:"min"`
		Close  float64 `json:"close"`
		Volume int64   `json:"Trading_Volume"`
	}

	var rows []row
	if err := json.Unmarshal(data, &rows); err != nil {
		return nil, fmt.Errorf("unmarshal prices: %w", err)
	}

	out := make([]models.StockPrice, 0, len(rows))
	for _, r := range rows {
		t, err := time.Parse("2006-01-02", r.Date)
		if err != nil {
			log.Printf("skip bad date %s: %v", r.Date, err)
			continue
		}
		out = append(out, models.StockPrice{
			StockID: stockID,
			Date:    t,
			Open:    r.Open,
			High:    r.Max,
			Low:     r.Min,
			Close:   r.Close,
			Volume:  r.Volume,
		})
	}
	return out, nil
}

// FetchInstitutional fetches TaiwanStockInstitutionalInvestorsBuySell and aggregates by date.
func (c *Client) FetchInstitutional(ctx context.Context, stockID, startDate string) ([]models.InstitutionalDay, error) {
	params := url.Values{
		"dataset":    {"TaiwanStockInstitutionalInvestorsBuySell"},
		"data_id":    {stockID},
		"start_date": {startDate},
	}

	data, err := c.get(ctx, params)
	if err != nil {
		return nil, fmt.Errorf("FetchInstitutional %s: %w", stockID, err)
	}

	type row struct {
		Date string `json:"date"`
		Name string `json:"name"`
		Buy  int64  `json:"buy"`
		Sell int64  `json:"sell"`
	}

	var rows []row
	if err := json.Unmarshal(data, &rows); err != nil {
		return nil, fmt.Errorf("unmarshal institutional: %w", err)
	}

	// Aggregate rows into InstitutionalDay by date
	byDate := make(map[string]*models.InstitutionalDay)
	for _, r := range rows {
		if _, ok := byDate[r.Date]; !ok {
			t, err := time.Parse("2006-01-02", r.Date)
			if err != nil {
				continue
			}
			byDate[r.Date] = &models.InstitutionalDay{StockID: stockID, Date: t}
		}
		d := byDate[r.Date]
		name := r.Name
		switch {
		case strings.Contains(name, "外資"):
			d.ForeignBuy += r.Buy
			d.ForeignSell += r.Sell
		case strings.Contains(name, "投信"):
			d.TrustBuy += r.Buy
			d.TrustSell += r.Sell
		case strings.Contains(name, "自營"):
			d.DealerBuy += r.Buy
			d.DealerSell += r.Sell
		}
	}

	out := make([]models.InstitutionalDay, 0, len(byDate))
	for _, d := range byDate {
		out = append(out, *d)
	}
	return out, nil
}
