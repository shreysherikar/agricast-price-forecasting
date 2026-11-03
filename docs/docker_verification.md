# Docker Verification Report

**Verification Date**: 2026-11-03  
**Environment**: Docker Compose on Windows (Docker Desktop v29.9.2 / Engine API 1.56)

---

## 1. Container Status

Command:
```bash
docker ps
```

Real Output:
```text
CONTAINER ID   IMAGE                               COMMAND                  CREATED          STATUS                    PORTS                                         NAMES
49c2219f8174   forecasting-project_work-gateway    "sh -c 'python manag…"   23 seconds ago   Up 11 seconds (healthy)   0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp   forecasting_gateway
22f0eb9b0579   forecasting-project_work-frontend   "/docker-entrypoint.…"   23 seconds ago   Up 16 seconds (healthy)   0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp   forecasting_frontend
139a1c230b1a   postgres:16-alpine                  "docker-entrypoint.s…"   23 seconds ago   Up 22 seconds (healthy)   5432/tcp                                      forecasting_postgres
961eb71142ff   forecasting-project_work-api        "sh -c 'uvicorn main…"   23 seconds ago   Up 22 seconds (healthy)   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp   forecasting_api
```

---

## 2. FastAPI Health Check (:8000/health)

Command:
```bash
curl.exe -s http://localhost:8000/health
```

Real Output:
```json
{"status":"HEALTHY","version":"1.0.0","database_connected":true,"artifacts_available":true,"model_loaded":true,"timestamp":"2026-11-03T07:51:03.323091+00:00"}
```

---

## 3. Django Gateway Health Check (:8080/api/health/)

Command:
```bash
curl.exe -s http://localhost:8080/api/health/
```

Real Output:
```json
{"status":"HEALTHY","service":"django_gateway","database_connected":true}
```

---

## 4. Live Forecast Query (:8080/api/forecast/latest/)

Command:
```bash
curl.exe -s http://localhost:8080/api/forecast/latest/
```

Real Output:
```json
{"run_id":null,"created_at":null,"model_version":"approved_stage3","origin":"2025-09-01","stale":false,"source":"fastapi_live","points":[{"month":"2025-10-01","point":15531.7,"lower_80":14423.5,"upper_80":16725.0,"lower_95":13869.2,"upper_95":17393.4},{"month":"2025-11-01","point":15411.2,"lower_80":13901.0,"upper_80":17085.5,"lower_95":13162.4,"upper_95":18044.2},{"month":"2025-12-01","point":15043.4,"lower_80":13279.5,"upper_80":17041.6,"lower_95":12431.1,"upper_95":18204.6},{"month":"2026-01-01","point":14737.0,"lower_80":12780.3,"upper_80":16993.2,"lower_95":11851.9,"upper_95":18324.3},{"month":"2026-02-01","point":14721.0,"lower_80":12572.0,"upper_80":17237.2,"lower_95":11564.5,"upper_95":18739.0},{"month":"2026-03-01","point":15532.7,"lower_80":13084.9,"upper_80":18438.4,"lower_95":11949.4,"upper_95":20190.5},{"month":"2026-04-01","point":15542.7,"lower_80":12931.1,"upper_80":18681.7,"lower_95":11731.2,"upper_95":20592.4},{"month":"2026-05-01","point":15535.3,"lower_80":12776.8,"upper_80":18889.3,"lower_95":11520.7,"upper_95":20948.8},{"month":"2026-06-01","point":15529.6,"lower_80":12635.1,"upper_80":19087.2,"lower_95":11328.2,"upper_95":21289.3},{"month":"2026-07-01","point":15960.7,"lower_80":12854.5,"upper_80":19817.6,"lower_95":11462.9,"upper_95":22223.4},{"month":"2026-08-01","point":15717.7,"lower_80":12537.1,"upper_80":19705.3,"lower_95":11122.9,"upper_95":22210.8},{"month":"2026-09-01","point":15894.5,"lower_80":12561.7,"upper_80":20111.6,"lower_95":11090.4,"upper_95":22779.6}]}
```
Verification:
- `source`: `"fastapi_live"`
- `stale`: `false`
- `points`: exactly 12 monthly points

---

## 5. Graceful Database Fallback Test (API Paused)

Command:
```bash
docker compose pause api
curl.exe -s "http://localhost:8080/api/forecast/latest/?force_refresh=true"
```

Real Output:
```json
{"run_id":1,"created_at":"2026-11-03T07:49:53.491254Z","model_version":"SARIMA(1,1,1)(1,0,0)[12]","origin":"2025-09","stale":true,"source":"database_fallback","points":[{"month":"2025-10-01","point":15531.7,"lower_80":14423.5,"upper_80":16725.0,"lower_95":13869.2,"upper_95":17393.4},{"month":"2025-11-01","point":15411.2,"lower_80":13901.0,"upper_80":17085.5,"lower_95":13162.4,"upper_95":18044.2},{"month":"2025-12-01","point":15043.4,"lower_80":13279.5,"upper_80":17041.6,"lower_95":12431.1,"upper_95":18204.6},{"month":"2026-01-01","point":14737.0,"lower_80":12780.3,"upper_80":16993.2,"lower_95":11851.9,"upper_95":18324.3},{"month":"2026-02-01","point":14721.0,"lower_80":12572.0,"upper_80":17237.2,"lower_95":11564.5,"upper_95":18739.0},{"month":"2026-03-01","point":15532.7,"lower_80":13084.9,"upper_80":18438.4,"lower_95":11949.4,"upper_95":20190.5},{"month":"2026-04-01","point":15542.7,"lower_80":12931.1,"upper_80":18681.7,"lower_95":11731.2,"upper_95":20592.4},{"month":"2026-05-01","point":15535.3,"lower_80":12776.8,"upper_80":18889.3,"lower_95":11520.7,"upper_95":20948.8},{"month":"2026-06-01","point":15529.6,"lower_80":12635.1,"upper_80":19087.2,"lower_95":11328.2,"upper_95":21289.3},{"month":"2026-07-01","point":15960.7,"lower_80":12854.5,"upper_80":19817.6,"lower_95":11462.9,"upper_95":22223.4},{"month":"2026-08-01","point":15717.7,"lower_80":12537.1,"upper_80":19705.3,"lower_95":11122.9,"upper_95":22210.8},{"month":"2026-09-01","point":15894.5,"lower_80":12561.7,"upper_80":20111.6,"lower_95":11090.4,"upper_95":22779.6}]}
```
Verification:
- `source`: `"database_fallback"`
- `stale`: `true`
- `points`: exactly 12 monthly points

---

## 6. Service Restoration Test (API Unpaused)

Command:
```bash
docker compose unpause api
curl.exe -s "http://localhost:8080/api/forecast/latest/?force_refresh=true"
```

Real Output:
```json
{"run_id":null,"created_at":null,"model_version":"approved_stage3","origin":"2025-09-01","stale":false,"source":"fastapi_live","points":[{"month":"2025-10-01","point":15531.7,"lower_80":14423.5,"upper_80":16725.0,"lower_95":13869.2,"upper_95":17393.4},{"month":"2025-11-01","point":15411.2,"lower_80":13901.0,"upper_80":17085.5,"lower_95":13162.4,"upper_95":18044.2},{"month":"2025-12-01","point":15043.4,"lower_80":13279.5,"upper_80":17041.6,"lower_95":12431.1,"upper_95":18204.6},{"month":"2026-01-01","point":14737.0,"lower_80":12780.3,"upper_80":16993.2,"lower_95":11851.9,"upper_95":18324.3},{"month":"2026-02-01","point":14721.0,"lower_80":12572.0,"upper_80":17237.2,"lower_95":11564.5,"upper_95":18739.0},{"month":"2026-03-01","point":15532.7,"lower_80":13084.9,"upper_80":18438.4,"lower_95":11949.4,"upper_95":20190.5},{"month":"2026-04-01","point":15542.7,"lower_80":12931.1,"upper_80":18681.7,"lower_95":11731.2,"upper_95":20592.4},{"month":"2026-05-01","point":15535.3,"lower_80":12776.8,"upper_80":18889.3,"lower_95":11520.7,"upper_95":20948.8},{"month":"2026-06-01","point":15529.6,"lower_80":12635.1,"upper_80":19087.2,"lower_95":11328.2,"upper_95":21289.3},{"month":"2026-07-01","point":15960.7,"lower_80":12854.5,"upper_80":19817.6,"lower_95":11462.9,"upper_95":22223.4},{"month":"2026-08-01","point":15717.7,"lower_80":12537.1,"upper_80":19705.3,"lower_95":11122.9,"upper_95":22210.8},{"month":"2026-09-01","point":15894.5,"lower_80":12561.7,"upper_80":20111.6,"lower_95":11090.4,"upper_95":22779.6}]}
```
Verification:
- Resumed upstream communication with `source`: `"fastapi_live"`, `stale`: `false`.
