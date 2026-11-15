// 설치 가능 조건을 맞추기 위한 최소 서비스 워커: 캐시 없이 그대로 네트워크로 넘긴다
self.addEventListener("install", e => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => e.respondWith(fetch(e.request)));
