import sys
# sys is required to access command-line arguments (e.g., sys.argv) for launching the PyQt application.

from PyQt5.QtWidgets import (
    QApplication,  # Core application class for PyQt
    QMainWindow,  # Base class for main application window
    QPushButton,  # Button widget
    QLabel,  # Label widget for displaying text
    QVBoxLayout,  # Vertical layout manager
    QWidget,  # Base class for all UI elements, used to create custom widgets
    QSlider,  # Slider widget for selecting a range value
    QTableWidget,  # Table widget to display rows and columns of data
    QTableWidgetItem,  # Represents each cell in a QTableWidget
    QLineEdit,  # Widget for single-line text input
    QHBoxLayout,  # Horizontal layout manager
    QPlainTextEdit, # Info box
    QDialog # for login screen
)
from PyQt5.QtCore import Qt
# Qt is used to set orientation (Horizontal/Vertical), alignment, and other constants.

from binance.client import Client
# Client class from the python-binance library to interact with the Binance API.

from binance.exceptions import BinanceAPIException
# BinanceAPIException is raised by the python-binance library when an API call fails.

from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET

# These enums represent constants used in placing orders (e.g., buy vs. sell).

from pprint import pformat


# Binance API keys (replace with your own keys).
# These are currently set to Testnet keys for demonstration.
API_KEY = 'no need for it actually'
API_SECRET = 'no need for it actually.'



class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        layout = QVBoxLayout(self)

        # Input for API Key
        self.api_key_input = QLineEdit(self)
        self.api_key_input.setPlaceholderText("API Key")
        layout.addWidget(self.api_key_input)

        # Input for API Secret
        self.api_secret_input = QLineEdit(self)
        self.api_secret_input.setPlaceholderText("API Secret")
        self.api_secret_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.api_secret_input)

        # Connect button to accept dialog
        self.connect_button = QPushButton("Connect", self)
        layout.addWidget(self.connect_button)
        self.connect_button.clicked.connect(self.accept)

    def get_credentials(self):
        """Return entered API key and secret."""
        return self.api_key_input.text(), self.api_secret_input.text()



class BinanceBot(QMainWindow):
    """
    Main class for our Binance Futures Testnet Bot.
    Inherits from QMainWindow to create a fully-featured window with menus, toolbars, etc.
    """

    def __init__(self, api_key, api_secret):
        """
        The constructor initializes the main window and variables.
        It then calls self.init_ui() to set up the interface.
        """
        super().__init__()

        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None  # Client is initialized only after clicking "Connect"

        # List of trading pairs loaded from Binance. Example: ['BTCUSDT', 'ETHUSDT', ...]
        self.trading_pairs = []

        # Currently selected pair from the table (e.g., 'BTCUSDT').
        self.selected_pair = ''

        # Default amount (in USDT) to trade. This is updated by the slider.
        self.selected_amount = 0.001

        # Flag to indicate if we're connected to Binance.
        self.is_connected = False

        # Initialize the user interface.
        self.init_ui()

    def init_ui(self):
        """
        Sets up the entire user interface: widgets, layout, and default states (disabled/enabled).
        """
        # Set window title and size.
        self.setWindowTitle("Binance Futures Testnet Bot")
        self.setGeometry(100, 100, 600, 500)


        # ========== Connection Status & Button ==========

        # Displays whether the bot is connected or not.
        self.connection_status_label = QLabel('Status: Not Connected', self)

        # Button to connect to the Binance Testnet.
        self.connect_button = QPushButton('Connect', self)
        self.connect_button.clicked.connect(self.connect_to_binance)

        # ========== Labels to Show Balance, Position, and PnL ==========

        # Displays the user's USDT balance in futures wallet.
        self.balance_label = QLabel('Balance: N/A', self)

        # Displays the user's open positions.
        self.position_label = QLabel('Position: N/A', self)

        # Displays the user's total unrealized PnL.
        self.pnl_label = QLabel('PnL: N/A', self)

        # ========== Searchable Pair Table ==========

        # QLineEdit for searching coin pairs.
        self.pair_input = QLineEdit(self)
        self.pair_input.setPlaceholderText("Search coin pair...")
        self.pair_input.textChanged.connect(self.filter_pairs)
        # Disable until connected.
        self.pair_input.setEnabled(False)

        # Table for displaying all available trading pairs.
        self.pair_table = QTableWidget(self)
        self.pair_table.setColumnCount(1)  # Only one column: Pair name
        self.pair_table.setHorizontalHeaderLabels(["Coin Pairs"])
        self.pair_table.setEditTriggers(QTableWidget.NoEditTriggers)  # Prevent direct editing
        self.pair_table.setSelectionBehavior(QTableWidget.SelectRows)  # Entire row is selected
        self.pair_table.setSelectionMode(QTableWidget.SingleSelection)  # Only one row at a time
        self.pair_table.cellClicked.connect(self.select_pair)  # Callback on row click
        # Disable until connected.
        self.pair_table.setEnabled(False)

        # Create second table for active positions
        self.active_positions_table = QTableWidget(self)
        self.active_positions_table.setColumnCount(1)
        self.active_positions_table.setHorizontalHeaderLabels(["Active Positions"])
        self.active_positions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.active_positions_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.active_positions_table.setSelectionMode(QTableWidget.SingleSelection)
        self.active_positions_table.cellClicked.connect(self.select_active_position)
        self.active_positions_table.setEnabled(False)  # Disable until connected

        # ========== Amount Slider ==========

        # Slider to choose the amount of USDT to trade.
        self.amount_slider = QSlider(Qt.Horizontal, self)
        self.amount_slider.setMinimum(1)  # Minimum 1 USDT
        self.amount_slider.setMaximum(1000)  # Maximum 1000 USDT
        self.amount_slider.setValue(10)  # Default value: 10 USDT
        self.amount_slider.valueChanged.connect(self.update_amount_label)
        # Disable until connected.
        self.amount_slider.setEnabled(False)

        # Label to show the amount selected with the slider.
        self.amount_label = QLabel(f'Selected Amount: {self.amount_slider.value()} USDT', self)

        # ========== Long and Short Buttons ==========

        # Button for going "Long" (this actually executes a short order, per the trick).
        self.long_button = QPushButton('Long', self)
        # Apply styling for visual appearance
        self.long_button.setStyleSheet("""
            background-color: #26A69A;  /* Light floral green */
            color: white;
            border-radius: 5px;
            padding: 5px;
            height: 30px;
        """)

        # Button for going "Short" (this actually executes a long order, per the trick).
        self.short_button = QPushButton('Short', self)
        self.short_button.setStyleSheet("""
            background-color: #E53935;  /* Light floral reddish */
            color: white;
            border-radius: 5px;
            padding: 5px;
            height: 30px;
        """)

        # Connect buttons to the appropriate methods.
        self.long_button.clicked.connect(self.open_short_position)
        self.short_button.clicked.connect(self.open_long_position)

        # Disable until connected.
        self.long_button.setEnabled(False)
        self.short_button.setEnabled(False)

        # ========== Layout Configuration ==========

        # Create a vertical layout to stack widgets top-down.
        layout = QVBoxLayout()

        # Add the connection label and button.
        layout.addWidget(self.connection_status_label)
        layout.addWidget(self.connect_button)

        # Add the balance, position, and PnL labels.
        layout.addWidget(self.balance_label)
        layout.addWidget(self.position_label)
        layout.addWidget(self.pnl_label)

        # Create a horizontal layout for searching pairs.
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search Pair: "))
        search_layout.addWidget(self.pair_input)
        layout.addLayout(search_layout)

        # Add the table of coin pairs.
        # Horizontal layout for both tables side by side
        tables_layout = QHBoxLayout()
        tables_layout.addWidget(self.pair_table)
        tables_layout.addWidget(self.active_positions_table)
        layout.addLayout(tables_layout)

        # Add the slider and label for the trading amount.
        layout.addWidget(QLabel("Select Position Amount:"))
        layout.addWidget(self.amount_slider)
        layout.addWidget(self.amount_label)

        # Add the "Long" and "Short" buttons.
        # Create a horizontal layout for the Long and Short buttons
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.long_button)
        button_layout.addWidget(self.short_button)
        layout.addLayout(button_layout)

        # Create the info box for displaying messages
        self.info_box = QPlainTextEdit(self)
        self.info_box.setReadOnly(True)
        layout.addWidget(self.info_box)

        # Add close positions button
        self.close_button = QPushButton('Close Positions', self)
        self.close_button.clicked.connect(self.close_positions)
        self.close_button.setEnabled(False)  # Disable until connected
        layout.addWidget(self.close_button)

        # Create a central widget, set its layout, and make it the main window's central widget.
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)



    def close_positions(self):
        """
        Closes all open positions for the selected coin.
        """
        if not self.is_connected:
            self.log_info("Cannot close positions. Not connected.")
            return
        try:
            # Fetch current positions for the selected pair
            positions = self.client.futures_position_information(symbol=self.selected_pair)
            if positions:
                pos = positions[0]
                position_amt = float(pos.get('positionAmt', 0))
                if position_amt == 0:
                    self.log_info(f"No open position for {self.selected_pair} to close.")
                    return
                # Determine side needed to close the position
                close_side = SIDE_SELL if position_amt > 0 else SIDE_BUY

                # Place a market order to close the entire position
                order = self.client.futures_create_order(
                    symbol=self.selected_pair,
                    side=close_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=abs(position_amt),
                    reduceOnly=True
                )
                self.log_info(f"Closed position for {self.selected_pair}:\n{pformat(order)}")
                self.update_account_details()
            else:
                self.log_info(f"No positions found for {self.selected_pair}.")
        except Exception as e:
            self.log_info(f"Error closing positions: {e}")

    def log_info(self, message: str):
        """
        Appends a message to the info box.
        """
        self.info_box.appendPlainText(str(message))

    def connect_to_binance(self):
        """
        Called when the user clicks the "Connect" button.
        Initializes the Binance client, tests the connection,
        and then enables the UI components if successful.
        """
        try:
            # Initialize the Binance Client using Testnet mode
            self.client = Client(self.api_key, self.api_secret, testnet=True)

            # Test connection by fetching server time
            server_time = self.client.futures_time()

            # Print raw server time to console
            print(f"Connected to Binance Testnet. Server time: {server_time}")

            # Log a pretty-formatted server time in the info box
            self.log_info(f"Connected to Binance Testnet.\nServer time:\n{pformat(server_time)}")

            # Update the internal connected status.
            self.is_connected = True

            # Update the UI to reflect successful connection.
            self.connection_status_label.setText("Status: Connected")
            self.connection_status_label.setStyleSheet("color: green")

            # Enable all UI components that were disabled prior to connection.
            self.pair_input.setEnabled(True)
            self.pair_table.setEnabled(True)
            self.amount_slider.setEnabled(True)
            self.long_button.setEnabled(True)
            self.short_button.setEnabled(True)
            self.close_button.setEnabled(True)
            self.active_positions_table.setEnabled(True)

            # Load trading pairs from Binance.
            self.load_trading_pairs()

            # Fetch and display account details like balance and positions.
            self.update_account_details()

        except Exception as e:
            # If anything goes wrong, log error and update UI status.
            self.log_info(f"Connection failed: {e}")
            self.connection_status_label.setText("Status: Connection Failed")
            self.connection_status_label.setStyleSheet("color: red")

    def load_trading_pairs(self):
        """
        Fetches information about all available futures trading pairs,
        extracts the symbol names, and populates them into the table.
        """
        try:
            # Retrieve futures exchange info from Binance, which includes symbol details.
            info = self.client.futures_exchange_info()

            # Parse out the symbol names (e.g., BTCUSDT, ETHUSDT, etc.).
            self.trading_pairs = [symbol['symbol'] for symbol in info['symbols']]

            # Populate the table widget with these pairs.
            self.populate_table(self.trading_pairs)
        except Exception as e:
            self.balance_label.setText('Error loading trading pairs.')
            self.log_info(f"Error: {e}")

    def populate_table(self, pairs):
        """
        Fills the QTableWidget with the given list of trading pairs.
        Each pair is added as a new row in the table.
        """
        # Set the row count to match the number of pairs.
        self.pair_table.setRowCount(len(pairs))

        # For each pair, create a QTableWidgetItem and insert it into the table.
        for row, pair in enumerate(pairs):
            item = QTableWidgetItem(pair)
            self.pair_table.setItem(row, 0, item)

    def filter_pairs(self):
        """
        Filters the trading pairs based on text input in the QLineEdit (pair_input).
        Only pairs containing the search string are displayed.
        """
        # Get the search text and convert to uppercase for case-insensitive match.
        search_text = self.pair_input.text().upper()

        # Filter the full list of trading_pairs by matching the search text.
        filtered_pairs = [pair for pair in self.trading_pairs if search_text in pair]

        # Re-populate the table with only the filtered results.
        self.populate_table(filtered_pairs)

    def select_pair(self, row, column):
        """
        Called when the user clicks a row in the pair_table.
        Updates self.selected_pair with the chosen pair's symbol.
        """
        # Get the text from the clicked cell.
        self.selected_pair = self.pair_table.item(row, 0).text()
        # Clear selection on the second table
        self.active_positions_table.clearSelection()

        # Log or self.log_info the chosen pair for debugging/verification.
        self.log_info(f"Selected Pair: {self.selected_pair}")

    def select_active_position(self, row, column):
        # When a coin is selected in the active positions table
        self.selected_pair = self.active_positions_table.item(row, 0).text()
        # Clear selection on the first table
        self.pair_table.clearSelection()
        self.log_info(f"Selected Active Position: {self.selected_pair}")

    def populate_active_positions_table(self):
        # Fetch all positions for the selected pair
        open_positions_info = self.client.futures_position_information()
        # Filter symbols with non-zero position amounts
        open_symbols = list({pos['symbol'] for pos in open_positions_info if float(pos.get('positionAmt', 0)) != 0})
        self.active_positions_table.setRowCount(len(open_symbols))
        for row, symbol in enumerate(open_symbols):
            item = QTableWidgetItem(symbol)
            self.active_positions_table.setItem(row, 0, item)

    def update_amount_label(self):
        """
        Called when the amount_slider value changes.
        Updates self.selected_amount and reflects it in amount_label.
        """
        self.selected_amount = self.amount_slider.value()
        self.amount_label.setText(f'Selected Amount: {self.selected_amount} USDT')

    def update_account_details(self):
        """
        Fetches and displays account-specific information:
        - Balance in USDT
        - Current open positions
        - Total unrealized profit/loss
        """

        try:
            # Retrieve the list of balances for the futures account.
            balance_info = self.client.futures_account_balance()

            # Find the USDT balance among all the returned assets.
            balance = next(item['balance'] for item in balance_info if item['asset'] == 'USDT')
            self.balance_label.setText(f'Balance: {balance} USDT')

            # Set maximum value of the slider to the current balance
            try:
                balance_value = float(balance)
                # Update slider maximum; converting to int as QSlider requires integer bounds.
                self.amount_slider.setMaximum(int(balance_value))
            except Exception as e:
                self.log_info(f"Error updating slider maximum: {e}")

            # Retrieve open positions (positionAmt != 0).
            positions = self.client.futures_position_information()
            open_positions = [pos for pos in positions if float(pos.get('positionAmt', 0)) != 0]

            # If any positions are open, concatenate them into a single string.
            if open_positions:
                position_details = "\n".join(
                    f"{pos['symbol']}: {pos['positionAmt']} @ {pos['entryPrice']} (PnL: {pos.get('unrealizedProfit', 'N/A')})"
                    for pos in open_positions
                )
                self.position_label.setText(f'Position: {position_details}')
            else:
                self.position_label.setText('Position: None')

            # Calculate the total unrealized PnL across all open positions.
            pnl = sum(float(pos.get('unrealizedProfit', 0)) for pos in positions if 'unrealizedProfit' in pos)
            self.pnl_label.setText(f'PnL: {pnl} USDT')

            # After setting pnl label inside update_account_details
            self.pnl_label.setText(f'PnL: {pnl} USDT')

            # Update the active positions table
            self.populate_active_positions_table()

        except Exception as e:
            # If there's any error (e.g., network issue), display it.
            self.balance_label.setText('Error fetching account details.')
            self.log_info(f"Error: {e}")

    def open_short_position(self):
        """
        Triggered when the user clicks the 'Long' button.
        According to the requirement, this method actually places a SHORT order.
        """
        self.place_order('SHORT')

    def open_long_position(self):
        """
        Triggered when the user clicks the 'Short' button.
        According to the requirement, this method actually places a LONG order.
        """
        self.place_order('LONG')

    def place_order(self, position_type):
        """
        Places a market order on the selected trading pair.
        - position_type: 'LONG' or 'SHORT' (in practice, 'LONG' means sell side, 'SHORT' means buy side).
        """
        if not self.is_connected:
            # If we haven't established connection, no orders can be placed.
            self.log_info("Cannot place orders. Not connected.")
            return

        try:
            # 1. Fetch the current price for the selected pair.
            ticker = self.client.futures_symbol_ticker(symbol=self.selected_pair)
            current_price = float(ticker['price'])

            # 2. Convert the user-selected USDT amount to base currency (e.g., BTC).
            qty = self.selected_amount / current_price

            # 3. Fetch symbol info to determine the pair's step size for quantity.
            info = self.client.futures_exchange_info()
            symbol_info = next(item for item in info['symbols'] if item['symbol'] == self.selected_pair)
            step_size = float(next(f['stepSize'] for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'))

            # 4. Adjust qty to match the precision/step size allowed by Binance.
            precision = len(str(step_size).split('.')[1])  # Number of decimal places
            qty = round(qty - (qty % step_size), precision)

            # 5. Check if we meet the minimum notional requirement (100 USDT).
            notional_value = qty * current_price
            min_notional = 100
            if notional_value < min_notional:
                self.log_info(f"Error: Notional value {notional_value} USDT is below the minimum required {min_notional} USDT.")
                return

            # 6. Determine the side: If position_type is 'LONG', we actually place a SELL order, and vice versa.
            side = SIDE_SELL if position_type == 'SHORT' else SIDE_BUY

            # 7. Place the market order with the calculated quantity.
            order = self.client.futures_create_order(
                symbol=self.selected_pair,
                side=side,
                type=ORDER_TYPE_MARKET,
                quantity=qty
            )
            print(f"{position_type} position opened (raw): {order}")
            self.log_info(f"{position_type} position opened:\n{pformat(order)}")

            # 8. Update account info (balance, positions, PnL) after placing the order.
            self.update_account_details()

        except Exception as e:
            # Catch any error (e.g., BinanceAPIException) and print the message.
            self.log_info(f'Error placing order: {e}')


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Show login dialog to get API credentials from the user
    login_dialog = LoginDialog()
    if login_dialog.exec_() == QDialog.Accepted:
        api_key, api_secret = login_dialog.get_credentials()

        # Instantiate the main window with user-provided credentials
        bot = BinanceBot(api_key, api_secret)
        bot.show()

        sys.exit(app.exec_())

