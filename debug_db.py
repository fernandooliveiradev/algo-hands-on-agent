import sqlite3
import json

conn = sqlite3.connect('data/aho.db')
cursor = conn.cursor()

print("=== CONTAGEM DE REGISTROS ===")
tables = [
    'aho_students',
    'aho_student_progress',
    'aho_module_progress',
    'aho_competency_progress',
    'aho_exercise_attempts',
    'aho_module_evidence',
    'aho_learning_events'
]

for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"{table}: {count}")

print("\n=== EVENTOS GRAVADOS ===")
cursor.execute("SELECT event_type, COUNT(*) FROM aho_learning_events GROUP BY event_type")
for event_type, count in cursor.fetchall():
    print(f"{event_type}: {count}")

print("\n=== AMOSTRA DE TUTOR_TURN EVENTS ===")
cursor.execute("SELECT payload_json FROM aho_learning_events WHERE event_type = 'tutor_turn' ORDER BY created_at DESC LIMIT 1")
result = cursor.fetchone()
if result:
    payload = result[0]
    data = json.loads(payload)
    print(f"\nLatest tutor_turn payload:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

print("\n=== DADOS EM AHO_STUDENTS ===")
cursor.execute("SELECT student_id, display_name FROM aho_students")
for student_id, display_name in cursor.fetchall():
    print(f"{student_id}: {display_name}")

# Ver dados de agno_sessions para ver mensagens
print("\n=== AGNO SESSIONS ===")
cursor.execute("SELECT COUNT(*) FROM agno_sessions")
session_count = cursor.fetchone()[0]
print(f"Total sessions: {session_count}")

# Ver dados de agno_memories para entender histórico
print("\n=== AGNO MEMORIES ===")
cursor.execute("SELECT COUNT(*) FROM agno_memories")
memory_count = cursor.fetchone()[0]
print(f"Total memories: {memory_count}")

conn.close()
