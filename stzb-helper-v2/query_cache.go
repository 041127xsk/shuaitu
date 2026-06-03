package main

import (
	"container/list"
	"fmt"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	queryCacheTTL     = 20 * time.Second
	queryCacheMaxSize = 32
)

type queryCacheEntry struct {
	key       string
	createdAt time.Time
	data      map[string]interface{}
}

type queryCache struct {
	sync.Mutex
	entries map[string]*list.Element
	order   *list.List
}

var teamWinRateQueryCache queryCache

func initQueryCache(cache *queryCache) {
	cache.entries = make(map[string]*list.Element, queryCacheMaxSize)
	cache.order = list.New()
}

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

	if cache.entries == nil {
		return nil, false
	}

	elem, ok := cache.entries[key]
	if !ok {
		return nil, false
	}

	entry := elem.Value.(*queryCacheEntry)
	if time.Since(entry.createdAt) > queryCacheTTL {
		cache.order.Remove(elem)
		delete(cache.entries, key)
		return nil, false
	}

	cache.order.MoveToFront(elem)
	return cloneQueryData(entry.data), true
}

func setCachedQueryData(cache *queryCache, key string, data map[string]interface{}) {
	cache.Lock()
	defer cache.Unlock()

	if cache.entries == nil {
		cache.entries = make(map[string]*list.Element, queryCacheMaxSize)
		cache.order = list.New()
	}

	if elem, ok := cache.entries[key]; ok {
		cache.order.Remove(elem)
		delete(cache.entries, key)
	}

	if cache.order.Len() >= queryCacheMaxSize {
		oldest := cache.order.Back()
		if oldest != nil {
			oldEntry := oldest.Value.(*queryCacheEntry)
			delete(cache.entries, oldEntry.key)
			cache.order.Remove(oldest)
		}
	}

	entry := &queryCacheEntry{
		key:       key,
		createdAt: time.Now(),
		data:      cloneQueryData(data),
	}
	elem := cache.order.PushFront(entry)
	cache.entries[key] = elem
}

func invalidateQueryCache(cache *queryCache) {
	cache.Lock()
	defer cache.Unlock()

	cache.entries = make(map[string]*list.Element, queryCacheMaxSize)
	if cache.order != nil {
		cache.order.Init()
	} else {
		cache.order = list.New()
	}
}

func cloneQueryData(data map[string]interface{}) map[string]interface{} {
	cloned := make(map[string]interface{}, len(data))
	for key, value := range data {
		cloned[key] = value
	}
	return cloned
}
