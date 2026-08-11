import sqlite3
import time
import subprocess
import requests
import logging

# Configure logging for terminal monitoring
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/terminal_breach.log"),
        logging.StreamHandler()
    ]
)

class TerminalBreachCore:
    def __init__(self, db_name="crypto_metrics.db"):
        self.db_name = db_name
        self._init_db()

    def _init_db(self):
        """Initialize the local SQLite database for asset tracking."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS btc_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    price_usd REAL NOT NULL
                )
            ''')
            conn.commit()
        logging.info("Database initialized successfully.")

    def fetch_btc_price(self):
        """Fetch current Bitcoin valuation from public API."""
        try:
            response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=5)
            data = response.json()
            price = float(data['data']['amount'])
            return price
        except Exception as e:
            logging.error(f"Failed to fetch BTC price: {e}")
            return None

    def log_btc_price(self):
        """Log current BTC price into the local database."""
        price = self.fetch_btc_price()
        if price:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO btc_logs (timestamp, price_usd) VALUES (?, ?)", (timestamp, price))
                conn.commit()
            logging.info(f"Logged BTC Price: ${price:,.2f} at {timestamp}")

    def execute_shell_command(self, command):
        """Execute a local shell command safely within the environment."""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logging.error(f"Command execution failed: {e.stderr.strip() if e.stderr else 'Unknown error'}")
            return None

    def assistant_router(self, wake_word, input_command):
        """Route commands based on active local assistant context."""
        assistants = ["jarvis", "vicky", "apex", "ods"]
        wake_word_lower = wake_word.lower()
        
        if wake_word_lower not in assistants:
            return "Unknown assistant registry."

        logging.info(f"Dispatching task to [{wake_word_lower.upper()}]: {input_command}")
        
        if "track btc" in input_command.lower():
            self.log_btc_price()
            return "Bitcoin metrics updated and logged."
        elif "run scan" in input_command.lower():
            output = self.execute_shell_command("uname -a")
            return f"System diagnostics complete: {output}"
        else:
            return f"{wake_word.capitalize()} standing by for next instruction."

if __name__ == "__main__":
    core = TerminalBreachCore()
    response = core.assistant_router("ODS", "track btc")
    print(response)
