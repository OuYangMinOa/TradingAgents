package config

import (
	"os"
	"strings"
)

type Config struct {
	DatabaseURL   string
	RedisURL      string
	FinMindToken  string
	WatchList     []string
}

var Default = &Config{
	DatabaseURL:  getEnv("GO_DATABASE_URL", "postgres://tradingagents:tradingagents@localhost:5432/tradingagents"),
	RedisURL:     getEnv("GO_REDIS_URL", "redis://localhost:6379"),
	FinMindToken: getEnv("FINMIND_API_TOKEN", ""),
	WatchList:    parseList(getEnv("WATCHLIST", "2330,2317,2454,2308,2881,2882,2412,2303,3711,2002,1301,2886,2891,2357,2382")),
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func parseList(s string) []string {
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if t := strings.TrimSpace(p); t != "" {
			out = append(out, t)
		}
	}
	return out
}
