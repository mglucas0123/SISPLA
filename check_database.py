import sqlite3

# Conectar ao banco de dados
conn = sqlite3.connect('instance/database.db')
cursor = conn.cursor()

# Verificar as colunas da tabela suppliers
cursor.execute('PRAGMA table_info(suppliers)')
columns = cursor.fetchall()

print("\n=== Colunas da tabela 'suppliers' ===\n")
for col in columns:
    print(f"  {col[1]}: {col[2]}")

conn.close()
print("\n✅ Verificação concluída!")
