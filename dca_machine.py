import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.simpledialog import askstring
import json
import time
import threading
import os
from dotenv import load_dotenv
from algosdk.v2client.algod import AlgodClient
from algosdk import mnemonic
from algosdk.account import address_from_private_key
from ffsdk.config import Network
from ffsdk.router.client import FolksRouterClient
from ffsdk.router.datatypes import SwapMode, SwapParams
from algosdk.encoding import msgpack_decode
from algosdk.error import AlgodHTTPError

# Load environment variables
load_dotenv()

# Prompt user for mnemonic and save it to .env
def prompt_and_save_mnemonic():
    mnemonic_input = askstring("Enter Mnemonic", "Please enter your wallet mnemonic:", show='*')
    if mnemonic_input:
        with open(".env", "a") as env_file:
            env_file.write(f"WALLET_MNEMONIC=\"{mnemonic_input}\"\n")
        os.environ["WALLET_MNEMONIC"] = mnemonic_input
        return mnemonic_input
    else:
        messagebox.showerror("Error", "Mnemonic is required!")
        app.quit()

# Get mnemonic from .env or prompt the user
def get_wallet_mnemonic():
    mnemonic_env = os.getenv("WALLET_MNEMONIC")
    if mnemonic_env:
        return mnemonic_env.strip('"')
    return prompt_and_save_mnemonic()

# Convert interval to seconds
def convert_interval(value, unit):
    value = int(value)
    if unit == "Minutes":
        return value * 60
    elif unit == "Hours":
        return value * 3600
    elif unit == "Days":
        return value * 86400
    return value  # Default to seconds

# Perform the DCA process
def dca_process(mnemonic_input, amount, asset_id, interval, num_purchases):
    global dca_running
    try:
        user_private_key = mnemonic.to_private_key(mnemonic_input)
        user_address = address_from_private_key(user_private_key)
        client = FolksRouterClient(Network.MAINNET)
        algod = AlgodClient("", "https://mainnet-api.algonode.cloud")

        log_text.insert(tk.END, "Starting DCA process...\n")
        for i in range(num_purchases):
            if not dca_running:
                log_text.insert(tk.END, "DCA process stopped by user.\n")
                log_text.update_idletasks()
                return

            try:
                log_text.insert(tk.END, f"Transaction {i + 1} of {num_purchases}...\n")
                log_text.update_idletasks()

                # Fetch and simulate quote
                swap_params = SwapParams(
                    fromAssetId=31566704,
                    toAssetId=asset_id,
                    amount=int(amount),
                    swapMode=SwapMode.FIXED_INPUT,
                )
                quote = client.fetchSwapQuote(swap_params)
                log_text.insert(tk.END, f"Quote Amount: {quote.quoteAmount / 1_000_000:.6f}\n")
                log_text.update_idletasks()

                # Submit transaction
                base64_txns = client.prepareSwapTransactions(swap_params, user_address, 10, quote)
                unsigned_txns = [msgpack_decode(txn) for txn in base64_txns]
                signed_txns = [txn.sign(user_private_key) for txn in unsigned_txns]
                txid = algod.send_transactions(signed_txns)
                log_text.insert(tk.END, f"Transaction ID: {txid}\n")
                log_text.update_idletasks()

            except AlgodHTTPError as e:
                log_text.insert(tk.END, f"Algod Error: {e}\n")
                return
            except Exception as e:
                log_text.insert(tk.END, f"Error in transaction: {e}\n")
                return

            if i < num_purchases - 1:
                log_text.insert(tk.END, f"Waiting for {interval // 60} minutes...\n")
                log_text.update_idletasks()
                time.sleep(interval)

        log_text.insert(tk.END, "DCA process complete.\n")
        messagebox.showinfo("DCA Complete", "All purchases have been completed.")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")

# Start DCA in a separate thread
def start_dca():
    global dca_running
    dca_running = True
    try:
        mnemonic_input = get_wallet_mnemonic()
        amount = float(amount_var.get()) * 1_000_000  # Convert to micro-units
        asset_id = int(asset_var.get())
        interval = convert_interval(interval_var.get(), interval_unit_var.get())
        num_purchases = int(purchases_var.get())

        dca_thread = threading.Thread(
            target=dca_process, args=(mnemonic_input, amount, asset_id, interval, num_purchases)
        )
        dca_thread.daemon = True
        dca_thread.start()
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")

# Stop DCA process
def stop_dca():
    global dca_running
    dca_running = False

# GUI Application
app = tk.Tk()
app.title("DCA Configuration")

# Input Fields
tk.Label(app, text="USDC per Purchase (e.g., 0.1)").grid(row=0, column=0, sticky="e")
amount_var = tk.StringVar(value="0.1")
tk.Entry(app, textvariable=amount_var).grid(row=0, column=1)

tk.Label(app, text="Asset ID to Purchase").grid(row=1, column=0, sticky="e")
asset_var = tk.StringVar(value="")
tk.Entry(app, textvariable=asset_var).grid(row=1, column=1)

tk.Label(app, text="Interval between Purchases").grid(row=2, column=0, sticky="e")
interval_var = tk.StringVar(value="1")
tk.Entry(app, textvariable=interval_var).grid(row=2, column=1)

tk.Label(app, text="Interval Unit").grid(row=2, column=2, sticky="w")
interval_unit_var = tk.StringVar(value="Minutes")
ttk.Combobox(app, textvariable=interval_unit_var, values=["Seconds", "Minutes", "Hours", "Days"]).grid(row=2, column=3)

tk.Label(app, text="Number of Purchases").grid(row=3, column=0, sticky="e")
purchases_var = tk.StringVar(value="")
tk.Entry(app, textvariable=purchases_var).grid(row=3, column=1)

# Buttons
tk.Button(app, text="Start DCA", command=start_dca).grid(row=4, column=0)
tk.Button(app, text="Stop DCA", command=stop_dca).grid(row=4, column=1)

# Log Area
log_text = tk.Text(app, height=10, width=70)
log_text.grid(row=5, column=0, columnspan=4)

app.mainloop()
