import pytest
import mysql.connector
from datetime import datetime
from unittest.mock import patch
import main
from main import (
    pridat_ukol_do_db,
    aktualizovat_stav_ukolu,
    smazat_ukol_podle_id,
    nacist_ukoly_z_db,
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


@pytest.fixture(autouse=True)
def setup_test_db_session(monkeypatch):
    """Vytvoření testovací DB a tabulky pouze jednou na začátku session."""
    monkeypatch.setattr(main, "DB_CONFIG", TEST_DB_CONFIG)
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

@pytest.fixture(autouse=True)
def truncate_ukoly_table():
    """Vyčistí tabulku ukoly před každým testem (rychlejší TRUNCATE)."""
    try:
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("TRUNCATE TABLE ukoly")
        cnx.commit()
        cursor.close()
        cnx.close()
    except mysql.connector.Error as err:
        pytest.fail(f"Chyba při čištění tabulky ukoly: {err}")


# ==================== TESTY PRO pridat_ukol_do_db() ====================


class TestPridatUkol:
    """Testy pro přidání úkolu"""

    def test_pridat_ukol_pozitivni(self):
        """POZITIVNÍ TEST: Přidání úkolu se správnými daty"""
        # Přidáme úkol do testovací databáze pomocí skutečné funkce
        pridat_ukol_do_db("Testovací úkol", "Popis testovacího úkolu")

        # Ověříme, že úkol byl přidán
        ukoly = nacist_ukoly_z_db()
        assert len(ukoly) == 1
        assert ukoly[0].nazev == "Testovací úkol"
        assert ukoly[0].popis == "Popis testovacího úkolu"
        assert ukoly[0].stav == "nezahájeno"

    def test_pridat_ukol_negativni_prazdny_nazev(self):
        """NEGATIVNÍ TEST: Přidání úkolu s prázdným názvem"""
        # Pokus přidat úkol s prázdným názvem - MySQL přijme, ale aplikace by měla validovat
        pridat_ukol_do_db("", "Popis úkolu")
        
        # MySQL vloží prázdný řetězec jako validní hodnotu
        ukoly = nacist_ukoly_z_db()
        assert len(ukoly) == 1
        assert ukoly[0].nazev == ""

    def test_pridat_ukol_negativni_specialni_znaky(self):
        """NEGATIVNÍ TEST: Přidání úkolu se speciálními znaky"""
        # Přidáme úkol s SQL injekcí (mělo by být bezpečné - parametrizované dotazy)
        pridat_ukol_do_db(
            "Úkol'; DROP TABLE ukoly; --",
            "Popis s nebezpečnými znaky"
        )

        # Ověříme, že tabulka stále existuje a úkol byl správně přidán
        ukoly = nacist_ukoly_z_db()
        assert len(ukoly) == 1
        assert ukoly[0].nazev == "Úkol'; DROP TABLE ukoly; --"


# ==================== TESTY PRO aktualizovat_stav_ukolu() ====================


class TestAktualizovatStav:
    """Testy pro aktualizaci stavu úkolu"""

    def test_aktualizovat_stav_pozitivni(self):
        """POZITIVNÍ TEST: Aktualizace stavu na 'probíhá'"""
        # Přidáme úkol
        pridat_ukol_do_db("Úkol ke změně", "Popis úkolu")
        ukoly = nacist_ukoly_z_db()
        ukol_id = ukoly[0].id

        # Změníme stav
        aktualizovat_stav_ukolu(ukol_id, "probíhá")

        # Ověříme změnu
        aktualizovane_ukoly = nacist_ukoly_z_db()
        assert len(aktualizovane_ukoly) == 1
        assert aktualizovane_ukoly[0].stav == "probíhá"

    def test_aktualizovat_stav_negativni_neexistujici_id(self):
        """NEGATIVNÍ TEST: Aktualizace stavu pro neexistující ID - očekáváme False"""
        result = aktualizovat_stav_ukolu(9999, "hotovo")
        assert result is False, "Funkce má vrátit False pro neexistující ID"
        ukoly = nacist_ukoly_z_db()
        assert len(ukoly) == 0

    def test_aktualizovat_stav_pozitivni_na_hotovo(self):
        """POZITIVNÍ TEST: Aktualizace stavu na 'hotovo'"""
        # Přidáme úkol
        pridat_ukol_do_db("Hotový úkol", "Popis")
        ukoly = nacist_ukoly_z_db()
        ukol_id = ukoly[0].id

        # Změníme na hotovo
        aktualizovat_stav_ukolu(ukol_id, "hotovo")

        # Ověříme
        updated = nacist_ukoly_z_db()
        assert updated[0].stav == "hotovo"


# ==================== TESTY PRO smazat_ukol_podle_id() ====================


class TestSmazatUkol:
    """Testy pro smazání úkolu"""

    def test_smazat_ukol_pozitivni(self):
        """POZITIVNÍ TEST: Smazání existujícího úkolu"""
        # Přidáme úkol
        pridat_ukol_do_db("Úkol k smazání", "Popis")
        ukoly = nacist_ukoly_z_db()
        assert len(ukoly) == 1
        ukol_id = ukoly[0].id

        # Smažeme úkol
        smazat_ukol_podle_id(ukol_id)

        # Ověříme, že úkol byl smazán
        updated_ukoly = nacist_ukoly_z_db()
        assert len(updated_ukoly) == 0

    def test_smazat_ukol_negativni_neexistujici_id(self):
        """NEGATIVNÍ TEST: Smazání neexistujícího úkolu - očekáváme False"""
        result = smazat_ukol_podle_id(9999)
        assert result is False, "Funkce má vrátit False pro neexistující ID"
        ukoly = nacist_ukoly_z_db()
        assert len(ukoly) == 0

    def test_smazat_ukol_pozitivni_viceukolu(self):
        """POZITIVNÍ TEST: Smazání konkrétního úkolu z více úkolů"""
        # Přidáme více úkolů
        pridat_ukol_do_db("Úkol 1", "Popis 1")
        pridat_ukol_do_db("Úkol 2", "Popis 2")
        pridat_ukol_do_db("Úkol 3", "Popis 3")

        ukoly = nacist_ukoly_z_db()
        assert len(ukoly) == 3
        
        # Smažeme druhý úkol
        ukol_id_k_smazani = ukoly[1].id
        smazat_ukol_podle_id(ukol_id_k_smazani)

        # Ověříme, že zbývají jen 2 úkoly
        updated_ukoly = nacist_ukoly_z_db()
        assert len(updated_ukoly) == 2
        assert updated_ukoly[0].nazev == "Úkol 1"
        assert updated_ukoly[1].nazev == "Úkol 3"


# ==================== INTEGRAČNÍ TEST ====================


class TestIntegrace:
    """Integrační test - kombinace operací"""

    def test_kompletni_workflow(self):
        """TEST: Komplexní pracovní tok"""
        # 1. Přidáme tři úkoly
        pridat_ukol_do_db("Nakoupit", "Nákup potravin")
        pridat_ukol_do_db("Vyčistit", "Vyčistit byt")
        pridat_ukol_do_db("Studovat", "Studie Python")

        ukoly = nacist_ukoly_z_db()
        assert len(ukoly) == 3

        # 2. Změníme stav prvního úkolu
        aktualizovat_stav_ukolu(ukoly[0].id, "probíhá")
        updated = nacist_ukoly_z_db()
        assert updated[0].stav == "probíhá"

        # 3. Smažeme druhý úkol
        smazat_ukol_podle_id(ukoly[1].id)
        final_ukoly = nacist_ukoly_z_db()
        assert len(final_ukoly) == 2

        # 4. Změníme stav zbývajícího úkolu na hotovo
        aktualizovat_stav_ukolu(final_ukoly[0].id, "hotovo")
        final_updated = nacist_ukoly_z_db()
        assert final_updated[0].stav == "hotovo"
