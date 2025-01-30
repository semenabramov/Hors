import pandas as pd
from sqlalchemy import create_engine, text
from rapidfuzz import process, fuzz

class OutletGroup:
    def __init__(self, name, outlet_id):
        self.name = name[:145]  # Обрезаем до 145 символов сразу
        self.clean_id = None  # ID после записи в outlets_clean
        self.outlet_ids = [outlet_id]  # Список всех точек, относящихся к этому имени

def connect_to_mysql(mysql_config):
    try:
        engine = create_engine(
            f"mysql+pymysql://{mysql_config['user']}:{mysql_config['password']}@{mysql_config['host']}/{mysql_config['database']}?charset=utf8mb4"
        )
        print("Успешное подключение к MySQL")
        return engine
    except Exception as e:
        print(f"Ошибка подключения к MySQL: {e}")
        return None

def fetch_and_deduplicate_outlets(mysql_config):
    engine = connect_to_mysql(mysql_config)
    if not engine:
        return
    
    with engine.connect() as conn:
        print("Удаляем старые записи из outlets_clean...")
        conn.execute(text("DELETE FROM outlets_clean WHERE 1=1"))
        conn.execute(text("ALTER TABLE outlets_clean AUTO_INCREMENT = 1"))
    
    query = "SELECT id, `Торг_точка_грязная` FROM outlets"
    df_outlets = pd.read_sql(query, engine)
    df_outlets["clean_name"] = df_outlets["Торг_точка_грязная"].str.lower().str.strip()
    
    total_outlets = len(df_outlets)
    outlet_groups = []
    
    for _, row in df_outlets.iterrows():
        name = row["clean_name"]
        outlet_id = row["id"]
        
        match_found = False
        for group in outlet_groups:
            score = fuzz.ratio(name, group.name)
            if score >= 85:
                group.outlet_ids.append(outlet_id)
                match_found = True
                break
        
        if not match_found:
            outlet_groups.append(OutletGroup(name, outlet_id))
    
    unique_names = [group.name for group in outlet_groups]
    total_unique_outlets = len(unique_names)
    
    df_clean = pd.DataFrame(unique_names, columns=["Торг_точка_чистый_адрес"])
    df_clean.to_sql("outlets_clean", con=engine, if_exists="append", index=False)
    
    clean_map = pd.read_sql("SELECT id, `Торг_точка_чистый_адрес` FROM outlets_clean", engine)
    clean_map["Торг_точка_чистый_адрес"] = clean_map["Торг_точка_чистый_адрес"].str.lower().str.strip()
    clean_name_to_id = {row["Торг_точка_чистый_адрес"]: row["id"] for _, row in clean_map.iterrows()}
    
    for group in outlet_groups:
        trimmed_name = group.name[:145]
        group.clean_id = clean_name_to_id.get(trimmed_name, None)
    
    df_outlets["outlet_clean_id"] = df_outlets["id"].map(
        {outlet_id: group.clean_id for group in outlet_groups for outlet_id in group.outlet_ids}
    )
    
    total_updated = 0
    with engine.begin() as conn:
        for _, row in df_outlets.iterrows():
            if pd.notna(row["outlet_clean_id"]):
                sql_query = f"UPDATE outlets SET outlet_clean_id = {row['outlet_clean_id']} WHERE id = {row['id']}"
                result = conn.execute(text(sql_query))
                total_updated += result.rowcount
    
    max_group_size = max(len(group.outlet_ids) for group in outlet_groups)
    
    print("\nСТАТИСТИКА ПОСЛЕ ДЕДУБЛИКАЦИИ:")
    print(f"Исходное количество торговых точек: {total_outlets}")
    print(f"Количество уникальных торговых точек после дедубликации: {total_unique_outlets}")
    print(f"Максимальное число объединенных записей в одну группу: {max_group_size}")
    print(f"Обновлено строк в outlets: {total_updated}")
    
mysql_config = {
    "host": "localhost",
    "user": "root",
    "password": "секретик:)",
    "database": "outlets_db",
}

fetch_and_deduplicate_outlets(mysql_config)

# Результат работы программы:

# Успешное подключение к MySQL
# Удаляем старые записи из outlets_clean...

# СТАТИСТИКА ПОСЛЕ ДЕДУБЛИКАЦИИ:
# Исходное количество торговых точек: 20208
# Количество уникальных торговых точек после дедубликации: 8767
# Максимальное число объединенных записей в одну группу: 66
# Обновлено строк в outlets: 20207    