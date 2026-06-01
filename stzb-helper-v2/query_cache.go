package main

import (
	"fmt"
	"strconv"
	"strings"
	"sync"
	"time"
)

type queryCacheEntry struct {
	key       string
	createdAt time.Time
	data      map[string]interface{}
}

type queryCache struct {
	sync.Mutex
	entry queryCacheEntry
}

const queryCacheTTL = 20 * time.Second

var teamWinRateQueryCache queryCache

func makeQueryCacheKey(parts ...interface{}) string {
	values := make([]string, 0, len(parts))
	for _, part := range parts {
		values = append(values, strings.TrimSpace(toCacheString(part)))
	}
	return strings.Join(values, "\x00")
}

func toCacheString(value interface{}) string {
	switch v := value.(type) {
	case string:
		return v
	case int:
		return strconv.Itoa(v)
	default:
		return fmt.Sprint(v)
	}
}

func getCachedQueryData(cache *queryCache, key string) (map[string]interface{}, bool) {
	cache.Lock()
	defer cache.Unlock()

	entry := cache.entry
	if entry.key != key || entry.data == nil || time.Since(entry.createdAt) > queryCacheTTL {
		return nil, false
	}
	return cloneQueryData(entry.data), true
}

func setCachedQueryData(cache *queryCache, key string, data map[string]interface{}) {
	cache.Lock()
	defer cache.Unlock()

	cache.entry = queryCacheEntry{
		key:       key,
		createdAt: time.Now(),
		data:      cloneQueryData(data),
	}
}

func invalidateQueryCache(cache *queryCache) {
	cache.Lock()
	defer cache.Unlock()
	cache.entry = queryCacheEntry{}
}

func cloneQueryData(data map[string]interface{}) map[string]interface{} {
	cloned := make(map[string]interface{}, len(data))
	for key, value := range data {
		cloned[key] = value
	}
	return cloned
}
