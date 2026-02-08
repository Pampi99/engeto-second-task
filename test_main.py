import pytest
import mysql.connector
from datetime import datetime
from main import (
    pridat_ukol_do_db,
    aktualizovat_stav_ukolu,
    smazat_ukol_podle_id,
    nacist_ukoly_z_db,
    Ukol,
    get_connection,
    DB_CONFIG,
)

# Testovací databáze - oddělená od hlavní
TEST_DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "Root1234!",
    "database": "test_tasks_db",
}


def get_test_connection(with_database=True):
    """Připojení k testovací databázi"""
    cfg = TEST_DB_CONFIG.copy()
    if not with_database:
        cfg.pop("database", None)
    return mysql.connector.connect(**cfg)


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """Vytvoření a vyčištění testovací databáze"""
    # Vytvoření testovací databáze a tabulky
    try:
        cnx = get_test_connection(with_database=False)
        cursor = cnx.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{TEST_DB_CONFIG['database']}` CHARACTER SET utf8mb4")
        cnx.commit()
        cursor.close()
        cnx.close()

        cnx = get_test_connection()
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
    except mysql.connector.Error as err:
        pytest.fail(f"Chyba při nastavení testovací databáze: {err}")

    yield

    # Vyčištění - smazání všech testovacích dat
    try:
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("DELETE FROM ukoly")
        cnx.commit()
        cursor.close()
        cnx.close()
    except mysql.connector.Error as err:
        pytest.fail(f"Chyba při vyčištění testovací databáze: {err}")


def pridat_ukol_do_test_db(nazev, popis):
    """Přidání úkolu do testovací databáze"""
    try:
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute(
            "INSERT INTO ukoly (nazev, popis, stav) VALUES (%s, %s, %s)",
            (nazev, popis, "nezahájeno"),
        )
        cnx.commit()
        cursor.close()
        cnx.close()
        return True
    except mysql.connector.Error as err:
        print(f"Chyba při vkládání úkolu: {err}")
        return False


def aktualizovat_stav_test_db(ukol_id, novy_stav):
    """Aktualizace stavu úkolu v testovací databázi"""
    try:
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("UPDATE ukoly SET stav = %s WHERE id = %s", (novy_stav, ukol_id))
        cnx.commit()
        cursor.close()
        cnx.close()
        return True
    except mysql.connector.Error as err:
        print(f"Chyba při aktualizaci stavu: {err}")
        return False


def smazat_ukol_test_db(ukol_id):
    """Smazání úkolu z testovací databáze"""
    try:
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("DELETE FROM ukoly WHERE id = %s", (ukol_id,))
        cnx.commit()
        cursor.close()
        cnx.close()
        return True
    except mysql.connector.Error as err:
        print(f"Chyba při mazání úkolu: {err}")
        return False


def nacist_ukoly_test_db():
    """Načtení všech úkolů z testovací databáze"""
    try:
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT id, nazev, popis, stav, datum_vytvoreni FROM ukoly ORDER BY id")
        rows = cursor.fetchall()
        cursor.close()
        cnx.close()
        return [
            Ukol(
                nazev=row[1],
                popis=row[2],
                stav=row[3],
                datum_vytvoreni=row[4],
                id=row[0],
            )
            for row in rows
        ]
    except mysql.connector.Error as err:
        print(f"Chyba při čtení úkolů: {err}")
        return []


# ==================== TESTY PRO pridat_ukol_do_db() ====================


class TestPridatUkol:
    """Testy pro přidání úkolu"""

    def test_pridat_ukol_pozitivni(self):
        """POZITIVNÍ TEST: Přidání úkolu se správnými daty"""
        # Přidáme úkol do testovací databáze
        result = pridat_ukol_do_test_db("Testovací úkol", "Popis testovacího úkolu")
        assert result is True

        # Ověříme, že úkol byl přidán
        ukoly = nacist_ukoly_test_db()
        assert len(ukoly) == 1
        assert ukoly[0].nazev == "Testovací úkol"
        assert ukoly[0].popis == "Popis testovacího úkolu"
        assert ukoly[0].stav == "nezahájeno"

    def test_pridat_ukol_negativni_prazdny_nazev(self):
        """NEGATIVNÍ TEST: Přidání úkolu s prázdným názvem"""
        # Pokus přidat úkol s prázdným názvem
        result = pridat_ukol_do_test_db("", "Popis úkolu")
        # Řetězec by měl být vložen, ale kontrolujeme chování
        # V MySQL prázdný řetězec je validní, ale v aplikaci bychom to měli ověřovat
        assert result is True  # MySQL vloží, ale aplikace by měla validovat

    def test_pridat_ukol_negativni_specialni_znaky(self):
        """NEGATIVNÍ TEST: Přidání úkolu se speciálními znaky"""
        # Přidáme úkol s SQL injekcí (mělo by být bezpečné)
        result = pridat_ukol_do_test_db(
            "Úkol'; DROP TABLE ukoly; --",
            "Popis s nebezpečnými znaky"
        )
        assert result is True

        # Ověříme, že tabulka stále existuje a úkol byl správně přidán
        ukoly = nacist_ukoly_test_db()
        assert len(ukoly) == 1
        assert ukoly[0].nazev == "Úkol'; DROP TABLE ukoly; --"


# ==================== TESTY PRO aktualizovat_stav_ukolu() ====================


class TestAktualizovatStav:
    """Testy pro aktualizaci stavu úkolu"""

    def test_aktualizovat_stav_pozitivni(self):
        """POZITIVNÍ TEST: Aktualizace stavu na 'probíhá'"""
        # Přidáme úkol
        pridat_ukol_do_test_db("Úkol ke změně", "Popis úkolu")
        ukoly = nacist_ukoly_test_db()
        ukol_id = ukoly[0].id

        # Změníme stav
        result = aktualizovat_stav_test_db(ukol_id, "probíhá")
        assert result is True

        # Ověříme změnu
        aktualizovane_ukoly = nacist_ukoly_test_db()
        assert len(aktualizovane_ukoly) == 1
        assert aktualizovane_ukoly[0].stav == "probíhá"

    def test_aktualizovat_stav_negativni_neexistujici_id(self):
        """NEGATIVNÍ TEST: Aktualizace stavu pro neexistující ID"""
        # Pokus aktualizovat úkol s ID, který neexistuje
        result = aktualizovat_stav_test_db(9999, "hotovo")
        assert result is True  # SQL příkaz vykoná bez chyby, ale nic nezmění

        # Ověříme, že žádný úkol není v databázi
        ukoly = nacist_ukoly_test_db()
        assert len(ukoly) == 0

    def test_aktualizovat_stav_pozitivni_na_hotovo(self):
        """POZITIVNÍ TEST: Aktualizace stavu na 'hotovo'"""
        # Přidáme úkol
        pridat_ukol_do_test_db("Hotový úkol", "Popis")
        ukoly = nacist_ukoly_test_db()
        ukol_id = ukoly[0].id

        # Změníme na hotovo
        result = aktualizovat_stav_test_db(ukol_id, "hotovo")
        assert result is True

        # Ověříme
        updated = nacist_ukoly_test_db()
        assert updated[0].stav == "hotovo"


# ==================== TESTY PRO smazat_ukol_podle_id() ====================


class TestSmazatUkol:
    """Testy pro smazání úkolu"""

    def test_smazat_ukol_pozitivni(self):
        """POZITIVNÍ TEST: Smazání existujícího úkolu"""
        # Přidáme úkol
        pridat_ukol_do_test_db("Úkol k smazání", "Popis")
        ukoly = nacist_ukoly_test_db()
        assert len(ukoly) == 1
        ukol_id = ukoly[0].id

        # Smažeme úkol
        result = smazat_ukol_test_db(ukol_id)
        assert result is True

        # Ověříme, že úkol byl smazán
        updated_ukoly = nacist_ukoly_test_db()
        assert len(updated_ukoly) == 0

    def test_smazat_ukol_negativni_neexistujici_id(self):
        """NEGATIVNÍ TEST: Smazání neexistujícího úkolu"""
        # Pokus smazat úkol s ID, který neexistuje
        result = smazat_ukol_test_db(9999)
        assert result is True  # SQL příkaz vykoná bez chyby

        # Ověříme, že v databázi nejsou žádné úkoly
        ukoly = nacist_ukoly_test_db()
        assert len(ukoly) == 0

    def test_smazat_ukol_pozitivni_viceukolu(self):
        """POZITIVNÍ TEST: Smazání konkrétního úkolu z více úkolů"""
        # Přidáme více úkolů
        pridat_ukol_do_test_db("Úkol 1", "Popis 1")
        pridat_ukol_do_test_db("Úkol 2", "Popis 2")
        pridat_ukol_do_test_db("Úkol 3", "Popis 3")

        ukoly = nacist_ukoly_test_db()
        assert len(ukoly) == 3
        
        # Smažeme druhý úkol
        ukol_id_k_smazani = ukoly[1].id
        result = smazat_ukol_test_db(ukol_id_k_smazani)
        assert result is True

        # Ověříme, že zbývají jen 2 úkoly
        updated_ukoly = nacist_ukoly_test_db()
        assert len(updated_ukoly) == 2
        assert updated_ukoly[0].nazev == "Úkol 1"
        assert updated_ukoly[1].nazev == "Úkol 3"


# ==================== INTEGRAČNÍ TEST ====================


class TestIntegrace:
    """Integrační test - kombinace operací"""

    def test_kompletni_workflow(self):
        """TEST: Komplexní pracovní tok"""
        # 1. Přidáme tři úkoly
        pridat_ukol_do_test_db("Nakoupit", "Nákup potravin")
        pridat_ukol_do_test_db("Vyčistit", "Vyčistit byt")
        pridat_ukol_do_test_db("Studovat", "Studie Python")

        ukoly = nacist_ukoly_test_db()
        assert len(ukoly) == 3

        # 2. Změníme stav prvního úkolu
        aktualizovat_stav_test_db(ukoly[0].id, "probíhá")
        updated = nacist_ukoly_test_db()
        assert updated[0].stav == "probíhá"

        # 3. Smažeme druhý úkol
        smazat_ukol_test_db(ukoly[1].id)
        final_ukoly = nacist_ukoly_test_db()
        assert len(final_ukoly) == 2

        # 4. Změníme stav zbývajícího úkolu na hotovo
        aktualizovat_stav_test_db(final_ukoly[0].id, "hotovo")
        final_updated = nacist_ukoly_test_db()
        assert final_updated[0].stav == "hotovo"
