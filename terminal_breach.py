import sqlite3
import time
import subprocess
import requests
import logging
import os
from datetime import datetime


# Configure logging for terminal monitoring
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/terminal_breach.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)


class TerminalBreachCore:
    def __init__(self, db_name="crypto_metrics.db", default_watchlist=None):
        self.db_name = db_name
        self.default_watchlist = default_watchlist or ["BTC", "ETH", "SOL"]
        self._init_db()

    def _init_db(self):
        """Initialize the local SQLite database for asset tracking."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    price_usd REAL NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS command_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    command TEXT NOT NULL,
                    output TEXT
                )
                """
            )
            conn.commit()
        logging.info("Database initialized successfully.")

    def fetch_asset_price(self, symbol="BTC"):
        """Fetch current price for a crypto asset from a public API."""
        symbol = symbol.upper().strip()
        if not symbol:
            raise ValueError("Asset symbol cannot be empty.")

        try:
            response = requests.get(
                f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot",
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
            return float(data["data"]["amount"])
        except requests.RequestException as exc:
            logging.error(f"Failed to fetch {symbol} price: {exc}")
            return None
        except (KeyError, TypeError, ValueError) as exc:
            logging.error(f"Unexpected response format while fetching {symbol}: {exc}")
            return None

    def log_asset_price(self, symbol="BTC"):
        """Log the current asset price into the local database."""
        price = self.fetch_asset_price(symbol)
        if price is None:
            return None

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO asset_logs (symbol, timestamp, price_usd) VALUES (?, ?, ?)",
                (symbol.upper(), timestamp, price),
            )
            conn.commit()

        logging.info(f"Logged {symbol.upper()} price: ${price:,.2f} at {timestamp}")
        return {"symbol": symbol.upper(), "price_usd": price, "timestamp": timestamp}

    def get_latest_price(self, symbol="BTC"):
        """Fetch the most recently logged price for a symbol."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT symbol, timestamp, price_usd
                FROM asset_logs
                WHERE symbol = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (symbol.upper(),),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return {
            "symbol": row[0],
            "timestamp": row[1],
            "price_usd": float(row[2]),
        }

    def get_price_history(self, symbol="BTC", limit=10):
        """Return recent price history for a symbol."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT symbol, timestamp, price_usd
                FROM asset_logs
                WHERE symbol = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (symbol.upper(), limit),
            )
            rows = cursor.fetchall()

        history = []
        for row in reversed(rows):
            history.append({
                "symbol": row[0],
                "timestamp": row[1],
                "price_usd": float(row[2]),
            })
        return history

    def execute_shell_command(self, command, timeout=10, allowed_commands=None):
        """Execute a local shell command safely within the environment."""
        if not command or not str(command).strip():
            return None

        allowed_commands = allowed_commands or [
            "uname -a",
            "whoami",
            "ls -la",
            "pwd",
            "df -h",
            "uptime",
            "date",
        ]

        normalized = str(command).strip()
        if normalized not in allowed_commands and not any(
            normalized.startswith(prefix) for prefix in ["echo ", "cat ", "ls ", "pwd", "uname", "whoami", "date", "df ", "uptime"]
        ):
            logging.warning(f"Blocked disallowed command: {normalized}")
            return "Command blocked by safety policy."

        try:
            result = subprocess.run(
                normalized,
                shell=True,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
            output = result.stdout.strip() or result.stderr.strip() or "Command completed without output."
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO command_logs (timestamp, command, output) VALUES (?, ?, ?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), normalized, output[:2000]),
                )
                conn.commit()
            return output
        except subprocess.TimeoutExpired:
            logging.error(f"Command timed out after {timeout} seconds: {normalized}")
            return "Command timed out."
        except Exception as exc:
            logging.error(f"Command execution failed: {exc}")
            return None

    def assistant_router(self, wake_word, input_command):
        """Route commands based on active local assistant context."""
        assistants = ["jarvis", "vicky", "apex", "ods"]
        wake_word_lower = (wake_word or "").lower()

        if wake_word_lower not in assistants:
            return "Unknown assistant registry."

        command = (input_command or "").lower().strip()
        logging.info(f"Dispatching task to [{wake_word_lower.upper()}]: {input_command}")

        if "track btc" in command or "track bitcoin" in command:
            self.log_asset_price("BTC")
            return "Bitcoin metrics updated and logged."
        elif "track eth" in command or "track ethereum" in command:
            self.log_asset_price("ETH")
            return "Ethereum metrics updated and logged."
        elif "track sol" in command or "track solana" in command:
            self.log_asset_price("SOL")
            return "Solana metrics updated and logged."
        elif "run scan" in command or "system scan" in command:
            output = self.execute_shell_command("uname -a")
            return f"System diagnostics complete: {output}"
        elif "latest" in command and "btc" in command:
            latest = self.get_latest_price("BTC")
            if latest is None:
                return "No BTC readings available yet."
            return f"Latest BTC price: ${latest['price_usd']:,.2f} at {latest['timestamp']}"
        elif "history" in command and "btc" in command:
            history = self.get_price_history("BTC", limit=5)
            if not history:
                return "No BTC history available yet."
            summary = "\n".join(
                f"{entry['timestamp']} -> ${entry['price_usd']:,.2f}"
                for entry in history
            )
            return f"Recent BTC history:\n{summary}"
        elif "status" in command:
            watchlist = []
            for symbol in self.default_watchlist:
                latest = self.get_latest_price(symbol)
                if latest:
                    watchlist.append(f"{symbol}: ${latest['price_usd']:,.2f} @ {latest['timestamp']}")
                else:
                    watchlist.append(f"{symbol}: no reading yet")
            return " | ".join(watchlist) if watchlist else "No readings logged yet."
        elif "help" in command or "menu" in command:
            return (
                "Available commands: 'track btc', 'track eth', 'track sol', "
                "'run scan', 'latest btc', 'history btc', 'status', 'help'."
            )
        else:
            return f"{wake_word.capitalize()} standing by for next instruction."


if __name__ == "__main__":
    core = TerminalBreachCore()
    print(core.assistant_router("ODS", "status"))
    print(core.assistant_router("ODS", "track btc"))
    print(core.assistant_router("ODS", "latest btc"))
    print(core.assistant_router("ODS", "help"))
