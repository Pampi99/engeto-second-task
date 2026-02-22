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

        # Ověříme přímým SQL dotazem do databáze
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT * FROM ukoly WHERE nazev = %s", ("Testovací úkol",))
        ukol = cursor.fetchone()
        cursor.close()
        cnx.close()
        
        assert ukol is not None
        assert ukol[1] == "Testovací úkol"  # nazev
        assert ukol[2] == "Popis testovacího úkolu"  # popis
        assert ukol[3] == "nezahájeno"  # stav

    def test_pridat_ukol_negativni_prazdny_nazev(self):
        """NEGATIVNÍ TEST: Přidání úkolu s prázdným názvem"""
        # Pokus přidat úkol s prázdným názvem - MySQL přijme, ale aplikace by měla validovat
        pridat_ukol_do_db("", "Popis úkolu")
        
        # Ověříme přímým SQL dotazem, že se prázdný úkol přidal
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT * FROM ukoly WHERE nazev = %s", ("",))
        ukol = cursor.fetchone()
        cursor.close()
        cnx.close()
        
        assert ukol is not None
        assert ukol[1] == ""  # nazev je prázdný

    def test_pridat_ukol_negativni_specialni_znaky(self):
        """NEGATIVNÍ TEST: Přidání úkolu se speciálními znaky"""
        # Přidáme úkol s SQL injekcí (mělo by být bezpečné - parametrizované dotazy)
        pridat_ukol_do_db(
            "Úkol'; DROP TABLE ukoly; --",
            "Popis s nebezpečnými znaky"
        )

        # Ověříme přímým SQL dotazem, že tabulka stále existuje a úkol byl správně přidán
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT * FROM ukoly WHERE nazev = %s", ("Úkol'; DROP TABLE ukoly; --",))
        ukol = cursor.fetchone()
        cursor.close()
        cnx.close()
        
        assert ukol is not None
        assert ukol[1] == "Úkol'; DROP TABLE ukoly; --"  # nazev


# ==================== TESTY PRO aktualizovat_stav_ukolu() ====================


class TestAktualizovatStav:
    """Testy pro aktualizaci stavu úkolu"""

    def test_aktualizovat_stav_pozitivni(self):
        """POZITIVNÍ TEST: Aktualizace stavu na 'probíhá'"""
        # Přidáme úkol
        pridat_ukol_do_db("Úkol ke změně", "Popis úkolu")
        
        # Získáme ID úkolu přímým SQL dotazem
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT id FROM ukoly WHERE nazev = %s", ("Úkol ke změně",))
        ukol_id = cursor.fetchone()[0]
        cursor.close()
        cnx.close()

        # Změníme stav
        aktualizovat_stav_ukolu(ukol_id, "probíhá")

        # Ověříme změnu přímým SQL dotazem
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT stav FROM ukoly WHERE id = %s", (ukol_id,))
        stav = cursor.fetchone()[0]
        cursor.close()
        cnx.close()
        
        assert stav == "probíhá"

    def test_aktualizovat_stav_negativni_neexistujici_id(self):
        """NEGATIVNÍ TEST: Aktualizace stavu pro neexistující ID - očekáváme False"""
        result = aktualizovat_stav_ukolu(9999, "hotovo")
        assert result is False, "Funkce má vrátit False pro neexistující ID"
        
        # Ověříme přímým SQL dotazem, že v databázi nejsou žádné úkoly
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT COUNT(*) FROM ukoly")
        count = cursor.fetchone()[0]
        cursor.close()
        cnx.close()
        
        assert count == 0

    def test_aktualizovat_stav_pozitivni_na_hotovo(self):
        """POZITIVNÍ TEST: Aktualizace stavu na 'hotovo'"""
        # Přidáme úkol
        pridat_ukol_do_db("Hotový úkol", "Popis")
        
        # Získáme ID úkolu přímým SQL dotazem
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT id FROM ukoly WHERE nazev = %s", ("Hotový úkol",))
        ukol_id = cursor.fetchone()[0]
        cursor.close()
        cnx.close()

        # Změníme na hotovo
        aktualizovat_stav_ukolu(ukol_id, "hotovo")

        # Ověříme přímým SQL dotazem
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT stav FROM ukoly WHERE id = %s", (ukol_id,))
        stav = cursor.fetchone()[0]
        cursor.close()
        cnx.close()
        
        assert stav == "hotovo"


# ==================== TESTY PRO smazat_ukol_podle_id() ====================


class TestSmazatUkol:
    """Testy pro smazání úkolu"""

    def test_smazat_ukol_pozitivni(self):
        """POZITIVNÍ TEST: Smazání existujícího úkolu"""
        # Přidáme úkol
        pridat_ukol_do_db("Úkol k smazání", "Popis")
        
        # Získáme ID úkolu
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT id FROM ukoly WHERE nazev = %s", ("Úkol k smazání",))
        ukol_id = cursor.fetchone()[0]
        cursor.close()
        cnx.close()

        # Smažeme úkol
        smazat_ukol_podle_id(ukol_id)

        # Ověříme přímým SQL dotazem, že úkol byl smazán
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT COUNT(*) FROM ukoly WHERE id = %s", (ukol_id,))
        count = cursor.fetchone()[0]
        cursor.close()
        cnx.close()
        
        assert count == 0

    def test_smazat_ukol_negativni_neexistujici_id(self):
        """NEGATIVNÍ TEST: Smazání neexistujícího úkolu - očekáváme False"""
        result = smazat_ukol_podle_id(9999)
        assert result is False, "Funkce má vrátit False pro neexistující ID"
        
        # Ověříme přímým SQL dotazem, že v databázi nejsou žádné úkoly
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT COUNT(*) FROM ukoly")
        count = cursor.fetchone()[0]
        cursor.close()
        cnx.close()
        
        assert count == 0

    def test_smazat_ukol_pozitivni_viceukolu(self):
        """POZITIVNÍ TEST: Smazání konkrétního úkolu z více úkolů"""
        # Přidáme více úkolů
        pridat_ukol_do_db("Úkol 1", "Popis 1")
        pridat_ukol_do_db("Úkol 2", "Popis 2")
        pridat_ukol_do_db("Úkol 3", "Popis 3")

        # Získáme ID druhého úkolu
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT id FROM ukoly WHERE nazev = %s", ("Úkol 2",))
        ukol_2_id = cursor.fetchone()[0]
        
        # Ověříme, že máme 3 úkoly
        cursor.execute("SELECT COUNT(*) FROM ukoly")
        count_before = cursor.fetchone()[0]
        assert count_before == 3
        
        cursor.close()
        cnx.close()
        
        # Smažeme druhý úkol
        smazat_ukol_podle_id(ukol_2_id)

        # Ověříme přímým SQL dotazem
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT COUNT(*) FROM ukoly")
        count_after = cursor.fetchone()[0]
        assert count_after == 2
        
        # Ověříme, že zbývají správné úkoly
        cursor.execute("SELECT nazev FROM ukoly ORDER BY id")
        remaining = cursor.fetchall()
        cursor.close()
        cnx.close()
        
        assert remaining[0][0] == "Úkol 1"
        assert remaining[1][0] == "Úkol 3"


# ==================== INTEGRAČNÍ TEST ====================


class TestIntegrace:
    """Integrační test - kombinace operací"""

    def test_kompletni_workflow(self):
        """TEST: Komplexní pracovní tok"""
        # 1. Přidáme tři úkoly
        pridat_ukol_do_db("Nakoupit", "Nákup potravin")
        pridat_ukol_do_db("Vyčistit", "Vyčistit byt")
        pridat_ukol_do_db("Studovat", "Studie Python")

        # Ověříme, že jsou 3 úkoly
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT COUNT(*) FROM ukoly")
        assert cursor.fetchone()[0] == 3
        
        # Získáme ID prvního úkolu
        cursor.execute("SELECT id FROM ukoly WHERE nazev = %s", ("Nakoupit",))
        ukol_1_id = cursor.fetchone()[0]
        
        # Získáme ID druhého úkolu
        cursor.execute("SELECT id FROM ukoly WHERE nazev = %s", ("Vyčistit",))
        ukol_2_id = cursor.fetchone()[0]
        
        cursor.close()
        cnx.close()

        # 2. Změníme stav prvního úkolu
        aktualizovat_stav_ukolu(ukol_1_id, "probíhá")
        
        # Ověříme stav prvního úkolu
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT stav FROM ukoly WHERE id = %s", (ukol_1_id,))
        assert cursor.fetchone()[0] == "probíhá"
        cursor.close()
        cnx.close()

        # 3. Smažeme druhý úkol
        smazat_ukol_podle_id(ukol_2_id)
        
        # Ověříme, že zbývají jen 2 úkoly
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT COUNT(*) FROM ukoly")
        assert cursor.fetchone()[0] == 2
        cursor.close()
        cnx.close()

        # 4. Změníme stav prvního úkolu na hotovo
        aktualizovat_stav_ukolu(ukol_1_id, "hotovo")
        
        # Ověříme konečný stav
        cnx = get_test_connection()
        cursor = cnx.cursor()
        cursor.execute("SELECT stav FROM ukoly WHERE id = %s", (ukol_1_id,))
        assert cursor.fetchone()[0] == "hotovo"
        cursor.close()
        cnx.close()
