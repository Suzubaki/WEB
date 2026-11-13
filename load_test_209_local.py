import requests
import concurrent.futures
import time
import statistics

URL = "http://127.0.0.1:3000"
USERNAME = "admin"
PASSWORD = "admin123"

START_DATE = "2020-01-01"
END_DATE = "2030-12-31"
USERS = 15

def test_user(i):
    s = requests.Session()

    try:
        t0 = time.perf_counter()

        r = s.post(
            URL + "/login",
            data={"username": USERNAME, "password": PASSWORD},
            timeout=60,
            allow_redirects=True
        )

        login_time = time.perf_counter() - t0

        if r.status_code != 200:
            return {
                "id": i,
                "status": f"LOGIN {r.status_code}",
                "login": login_time,
                "excel": None,
                "size": 0
            }

        t1 = time.perf_counter()

        r = s.post(
            URL + "/generate_report",
            data={
                "report_type": "form_209_apk",
                "format": "excel",
                "start_date": START_DATE,
                "end_date": END_DATE,
                "farm_filter": "all"
            },
            timeout=300
        )

        excel_time = time.perf_counter() - t1

        return {
            "id": i,
            "status": r.status_code,
            "login": login_time,
            "excel": excel_time,
            "size": len(r.content)
        }

    except Exception as e:
        return {
            "id": i,
            "status": "ERROR: " + str(e),
            "login": None,
            "excel": None,
            "size": 0
        }

print("=" * 75)
print("ЛОКАЛЬНЫЙ СТРЕСС-ТЕСТ 209-АПК")
print("=" * 75)
print(f"URL: {URL}")
print(f"Пользователей: {USERS}")
print(f"Период: {START_DATE} — {END_DATE}")
print()
print("Запускаю 15 одновременных пользователей...")
print()

total_start = time.perf_counter()

with concurrent.futures.ThreadPoolExecutor(max_workers=USERS) as executor:
    results = list(executor.map(test_user, range(1, USERS + 1)))

total_time = time.perf_counter() - total_start

print("=" * 75)
print("РЕЗУЛЬТАТ")
print("=" * 75)

for r in results:
    if r["excel"] is not None:
        print(
            f"User {r['id']:2} | "
            f"status={r['status']} | "
            f"login={r['login']:.2f}s | "
            f"209={r['excel']:.2f}s | "
            f"size={r['size']:,} bytes"
        )
    else:
        print(f"User {r['id']:2} | status={r['status']}")

successful = [
    r["excel"] for r in results
    if r["status"] == 200 and r["excel"] is not None
]

sizes = [
    r["size"] for r in results
    if r["status"] == 200
]

print()
print("=" * 75)
print(f"Общее время теста: {total_time:.2f} сек")
print(f"Успешных отчётов: {len(successful)}/{USERS}")

if successful:
    print(f"Среднее время 209: {statistics.mean(successful):.2f} сек")
    print(f"Минимум: {min(successful):.2f} сек")
    print(f"Максимум: {max(successful):.2f} сек")

if sizes:
    print()
    print(f"Размер Excel: {min(sizes):,} — {max(sizes):,} байт")
    print(f"Средний размер: {statistics.mean(sizes):,.0f} байт")

print("=" * 75)
