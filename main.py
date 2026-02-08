import mysql.connector
from mysql.connector import errorcode
from datetime import datetime


def tiskni_menu():
	# tiskne pouze menu
	print("Správce úkolů - Hlavní menu")
	print("1. Přidat nový úkol")
	print("2. Zobrazit všechny úkoly")
	print("3. Odstranit úkol")
	print("4. Změnit stav úkolu")
	print("5. Konec programu")

# přidaná třída pro úkoly
class Ukol:
	def __init__(self, nazev, popis, stav="nezahájeno", datum_vytvoreni=None, id=None):
		self.id = id
		self.nazev = nazev
		self.popis = popis
		self.stav = stav
		self.datum_vytvoreni = datum_vytvoreni

# Database configuration (local MySQL with root/root)
DB_CONFIG = {
	"host": "127.0.0.1",
	"user": "root",
	"password": "Root1234!",
	"database": "tasks_db",
}


def get_connection(with_database=True):
	cfg = DB_CONFIG.copy()
	# connect without database when creating it
	if not with_database:
		cfg.pop("database", None)
	return mysql.connector.connect(**cfg)


def pripojeni_db():
	# Připojení k MySQL databázi
	try:
		cnx = get_connection(with_database=False)
		cursor = cnx.cursor()
		cursor.execute("CREATE DATABASE IF NOT EXISTS `{}` CHARACTER SET utf8mb4".format(DB_CONFIG["database"]))
		cnx.commit()
		cursor.close()
		cnx.close()
		return True
	except mysql.connector.Error as err:
		print("Chyba při připojení k databázi:", err)
		return False

def vytvoreni_tabulky():
	# Vytvoření tabulky ukoly, pokud neexistuje
	try:
		cnx = get_connection()
		cursor = cnx.cursor()
		cursor.execute(
			"""
			CREATE TABLE IF NOT EXISTS ukoly (
				id INT AUTO_INCREMENT PRIMARY KEY,
				nazev VARCHAR(255) NOT NULL,
				popis TEXT NOT NULL,
				stav ENUM('nezahájeno', 'hotovo', 'probíhá') DEFAULT 'nezahájeno',
				datum_vytvoreni TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
			"""
		)
		cnx.commit()
		cursor.close()
		cnx.close()
		return True
	except mysql.connector.Error as err:
		print("Chyba při vytváření tabulky:", err)
		return False

def pridat_ukol_do_db(nazev, popis):
	try:
		cnx = get_connection()
		cursor = cnx.cursor()
		cursor.execute(
			"INSERT INTO ukoly (nazev, popis, stav) VALUES (%s, %s, %s)", 
			(nazev, popis, "nezahájeno")
		)
		cnx.commit()
		cursor.close()
		cnx.close()
	except mysql.connector.Error as err:
		print("Chyba při vkládání úkolu:", err)


def pridat_ukol():
	# validace a uložení do DB
	while True:
		nazev = input("Zadejte název úkolu: ").strip()
		if not nazev:
			print("Název nesmí být prázdný. Zkuste to znovu.\n")
			continue
		break
	while True:
		popis = input("Zadejte popis úkolu: ").strip()
		if not popis:
			print("Popis nesmí být prázdný. Zkuste to znovu.\n")
			continue
		break
	pridat_ukol_do_db(nazev, popis)
	print(f"Úkol '{nazev}' byl přidán.")
	print()

def nacist_ukoly_z_db():
	try:
		cnx = get_connection()
		cursor = cnx.cursor()
		cursor.execute("SELECT id, nazev, popis, stav, datum_vytvoreni FROM ukoly ORDER BY id")
		rows = cursor.fetchall()
		cursor.close()
		cnx.close()
		return [Ukol(nazev=row[1], popis=row[2], stav=row[3], datum_vytvoreni=row[4], id=row[0]) for row in rows]
	except mysql.connector.Error as err:
		print("Chyba při čtení úkolů:", err)
		return []


def zobrazit_ukoly():
	print("Seznam úkolů:")
	seznam = nacist_ukoly_z_db()
	if not seznam:
		print("Žádné úkoly.")
		print()
		return
	for index, ukol in enumerate(seznam, start=1):
		datum_str = ukol.datum_vytvoreni.strftime("%d.%m.%Y %H:%M:%S") if isinstance(ukol.datum_vytvoreni, datetime) else str(ukol.datum_vytvoreni)
		print(f"{index}. {ukol.nazev}")
		print(f"   Popis: {ukol.popis}")
		print(f"   Stav: {ukol.stav}")
		print(f"   Vytvořeno: {datum_str}")
	print()

def smazat_ukol_podle_id(ukol_id):
	try:
		cnx = get_connection()
		cursor = cnx.cursor()
		cursor.execute("DELETE FROM ukoly WHERE id = %s", (ukol_id,))
		cnx.commit()
		cursor.close()
		cnx.close()
	except mysql.connector.Error as err:
		print("Chyba při mazání úkolu:", err)


def odstranit_ukol():
	seznam = nacist_ukoly_z_db()
	if not seznam:
		print("Žádné úkoly k odstranění.\n")
		return
	for index, ukol in enumerate(seznam, start=1):
		print(f"{index}. {ukol.nazev} - {ukol.popis}")
	input_index = input("Zadejte číslo úkolu, který chcete odstranit: ").strip()
	if not input_index.isdigit():
		print("Zadáno neplatné číslo.\n")
		return
	idx = int(input_index)
	if 1 <= idx <= len(seznam):
		ukol_k_smazani = seznam[idx - 1]
		smazat_ukol_podle_id(ukol_k_smazani.id)
		print(f"Úkol '{ukol_k_smazani.nazev}' byl odstraněn.\n")
		return
	print("Číslo není v rozsahu. Zkuste to znovu.\n")

def aktualizovat_stav_ukolu(ukol_id, novy_stav):
	try:
		cnx = get_connection()
		cursor = cnx.cursor()
		cursor.execute("UPDATE ukoly SET stav = %s WHERE id = %s", (novy_stav, ukol_id))
		cnx.commit()
		cursor.close()
		cnx.close()
	except mysql.connector.Error as err:
		print("Chyba při aktualizaci stavu úkolu:", err)

def aktualizovat_ukol():
	seznam = nacist_ukoly_z_db()
	if not seznam:
		print("Žádné úkoly k úpravě.\n")
		return
	for index, ukol in enumerate(seznam, start=1):
		print(f"{index}. {ukol.nazev} - Stav: {ukol.stav}")
	input_index = input("Zadejte číslo úkolu, který chcete upravit: ").strip()
	if not input_index.isdigit():
		print("Zadáno neplatné číslo.\n")
		return
	idx = int(input_index)
	if not (1 <= idx <= len(seznam)):
		print("Číslo není v rozsahu. Zkuste to znovu.\n")
		return
	
	ukol_k_zmene = seznam[idx - 1]
	print(f"Dostupné stavy: 1. nezahájeno, 2. probíhá, 3. hotovo")
	stav_choice = input("Vyberte nový stav (1-3): ").strip()
	stav_mapa = {"1": "nezahájeno", "2": "probíhá", "3": "hotovo"}
	if stav_choice not in stav_mapa:
		print("Neplatný výběr.\n")
		return
	novy_stav = stav_mapa[stav_choice]
	aktualizovat_stav_ukolu(ukol_k_zmene.id, novy_stav)
	print(f"Stav úkolu '{ukol_k_zmene.nazev}' byl změněn na '{novy_stav}'.\n")

def ukoncit_program():
	print("Konec programu.")
	print()

def ziskej_volbu():
	# Vrátí 1-5 pokud je vstup platný, jinak None
	choice = input("Vyberte možnost (1-5): ")
	print()
	if choice in ("1", "2", "3", "4", "5"):
		return int(choice)
	return None

def hlavni_menu():
	while True:
		tiskni_menu()
		volba = ziskej_volbu()
		if volba is None:
			print("Neplatná volba. Zadejte číslo od 1 do 5.\n")
			continue
		if volba == 1:
			pridat_ukol()
		elif volba == 2:
			zobrazit_ukoly()
		elif volba == 3:
			odstranit_ukol()
		elif volba == 4:
			aktualizovat_ukol()
		else:  # 5
			ukoncit_program()
			break

def main():
	if not pripojeni_db():
		return
	
	if not vytvoreni_tabulky():
		return

	hlavni_menu()


if __name__ == "__main__":
	main()

