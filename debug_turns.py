import sqlite3
import json

conn = sqlite3.connect('data/aho.db')
cursor = conn.cursor()

print("=== ÚLTIMOS 5 TUTOR_TURN EVENTS ===\n")

cursor.execute("""
SELECT event_type, payload_json 
FROM aho_learning_events 
WHERE event_type = 'tutor_turn' 
ORDER BY created_at DESC 
LIMIT 5
""")

for i, (event_type, payload) in enumerate(cursor.fetchall()):
    data = json.loads(payload)
    print(f"Event {i+1}:")
    print(f"  Turn type: {data.get('turn_type')}")
    print(f"  Module: {data.get('module_id')}")
    print(f"  Competency: {data.get('competency_key')}")
    print(f"  Next action: {data.get('next_action')}")
    print(f"  Evaluation: {data.get('evaluation')}")
    print()

conn.close()
