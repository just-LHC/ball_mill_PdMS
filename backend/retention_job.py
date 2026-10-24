import json

from db_engine import init_alert_db_table, purge_expired_alert_data


def main():
    init_alert_db_table()
    result = purge_expired_alert_data()
    print(json.dumps(result))


if __name__ == "__main__":
    main()