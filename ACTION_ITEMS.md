# Quick Action Items to Prevent Recurrence

Based on the retrospective, here are the immediate actions you should take:

## 🔴 High Priority (Do This Week)

### 1. Rename env-config.html to env-config.js
**Why:** Makes file purpose clear, prevents confusion

**How:**
```bash
cd ai-market-studio-ui
mv env-config.html env-config.js

# Update index.html
sed -i 's/env-config.html/env-config.js/g' index.html

# Update Dockerfile
sed -i 's/env-config.html/env-config.js/g' Dockerfile

# Update docker-entrypoint.sh
sed -i 's/env-config.html/env-config.js/g' docker-entrypoint.sh

# Rebuild and deploy
docker build --no-cache -t gcr.io/gen-lang-client-0896070179/ai-market-studio-ui:latest .
docker push gcr.io/gen-lang-client-0896070179/ai-market-studio-ui:latest
kubectl rollout restart deployment/ai-market-studio-ui
```

### 2. Add Cache-Control Headers
**Why:** Prevents caching of configuration file

**How:** Update `nginx.conf`:
```nginx
server {
    listen 80;
    server_name localhost;

    root /usr/share/nginx/html;
    index index.html;

    # Prevent caching of config file
    location = /env-config.js {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Enable gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    # Cache static assets (but not config)
    location ~* \.(jpg|jpeg|png|gif|ico|css|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 3. Add Docker Image Verification Script
**Why:** Ensures Docker image has correct files before deployment

**How:** Create `verify-image.sh`:
```bash
#!/bin/bash
set -e

IMAGE="gcr.io/gen-lang-client-0896070179/ai-market-studio-ui:latest"

echo "Verifying Docker image: $IMAGE"
echo ""

echo "1. Checking env-config.js exists..."
docker run --rm $IMAGE sh -c "test -f /usr/share/nginx/html/env-config.js && echo '✓ File exists'"

echo "2. Checking env-config.js content..."
CONTENT=$(docker run --rm $IMAGE cat /usr/share/nginx/html/env-config.js)
if echo "$CONTENT" | grep -q "window.ENV"; then
    echo "✓ Contains window.ENV"
else
    echo "✗ Missing window.ENV"
    exit 1
fi

if echo "$CONTENT" | grep -q "API_BASE_URL"; then
    echo "✓ Contains API_BASE_URL"
else
    echo "✗ Missing API_BASE_URL"
    exit 1
fi

echo ""
echo "✓ Image verification passed!"
```

## 🟡 Medium Priority (Do This Month)

### 4. Add Browser-Based E2E Tests
**Why:** Catches JavaScript execution issues

**How:** Use Playwright (already have the skill):
```bash
# Install Playwright
npm install -D @playwright/test

# Create test file: tests/e2e.spec.js
```

```javascript
const { test, expect } = require('@playwright/test');

test('UI can connect to backend', async ({ page }) => {
  await page.goto('http://136.116.205.168');

  // Check API_BASE_URL is set correctly
  const apiUrl = await page.evaluate(() => window.ENV?.API_BASE_URL);
  expect(apiUrl).toBe('http://35.224.3.54');

  // Try a query
  await page.fill('textarea', 'What is EUR/USD?');
  await page.click('button:has-text("Send")');

  // Wait for response (not error)
  await expect(page.locator('.bubble.assistant')).toBeVisible({ timeout: 30000 });
  await expect(page.locator('.bubble.error')).not.toBeVisible();
});
```

### 5. Implement /api/config Endpoint
**Why:** More robust than file-based config

**Backend (ai-market-studio):**
```python
@app.get("/api/config")
async def get_config():
    return {
        "api_base_url": os.getenv("API_BASE_URL", "http://localhost:8000"),
        "version": "1.0.0",
        "features": {
            "rag_enabled": bool(os.getenv("RAG_SERVICE_URL"))
        }
    }
```

**Frontend:**
```javascript
// Fetch config on load
async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    const config = await res.json();
    window.ENV = { API_BASE_URL: config.api_base_url };
  } catch (e) {
    console.error('Failed to load config, using default');
    window.ENV = { API_BASE_URL: 'http://localhost:8000' };
  }
}
```

## 🟢 Low Priority (Nice to Have)

### 6. Use Image Digests Instead of :latest
**Why:** Prevents ambiguity about which version is deployed

**How:**
```bash
# Build and get digest
docker build -t gcr.io/gen-lang-client-0896070179/ai-market-studio-ui:v1.0.0 .
docker push gcr.io/gen-lang-client-0896070179/ai-market-studio-ui:v1.0.0
DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' gcr.io/gen-lang-client-0896070179/ai-market-studio-ui:v1.0.0)

# Update deployment.yaml
image: $DIGEST
```

### 7. Add Monitoring
**Why:** Detect issues before users report them

**How:** Add to backend:
```python
from prometheus_client import Counter, Histogram

request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')

@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    request_count.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()

    request_duration.observe(duration)
    return response
```

---

## Deployment Checklist (Use This Every Time)

```markdown
## Pre-Deployment
- [ ] Code changes committed and pushed
- [ ] Docker image built with --no-cache
- [ ] Image contents verified (run verify-image.sh)
- [ ] Tests passing locally

## Deployment
- [ ] Image pushed to GCR
- [ ] ConfigMap updated (if needed)
- [ ] Deployment updated
- [ ] Pods restarted

## Post-Deployment
- [ ] Wait 30 seconds for cache to clear
- [ ] Run test_e2e_connectivity.sh
- [ ] Run test_browser_simulation.sh
- [ ] Test in actual browser with hard refresh
- [ ] Check logs for errors

## Rollback Plan
- [ ] Previous image tag documented
- [ ] Rollback command ready: kubectl rollout undo deployment/<name>
```

---

## Summary

The most important actions to prevent this from happening again:

1. **Rename to .js** - Makes file type clear
2. **Add cache headers** - Prevents caching issues
3. **Verify images** - Catches build problems early
4. **Test in browsers** - Catches JavaScript issues
5. **Use deployment checklist** - Ensures nothing is missed

Start with items 1-3 this week. They're quick wins that will prevent 90% of similar issues.
