import tkinter as tk
from tkinter import ttk, messagebox

class ExpenseSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("💰 Expense Splitter")
        self.root.configure(bg="#f0f4f8")
        self.root.geometry("700x700")
        self.root.resizable(False, False)
        self.root.state("zoomed")  # if you want a normal maximized window


        self.people_data = []

        title_label = tk.Label(root, text="💸 Split Expense App", font=("Segoe UI", 22, "bold"), bg="#f0f4f8", fg="#2c3e50")
        title_label.pack(pady=20)

        # Frame for input
        self.input_frame = tk.Frame(root, bg="#f0f4f8")
        self.input_frame.pack()

        self._add_input_field("Total People:", 0)
        self.people_entry = self._add_entry_field(0)

        self._add_input_field("Total Amount (₹):", 1)
        self.amount_entry = self._add_entry_field(1)

        self.submit_btn = tk.Button(
            self.input_frame,
            text="➡ Next",
            font=("Segoe UI", 11, "bold"),
            bg="#27ae60",
            fg="white",
            activebackground="#1e8449",
            cursor="hand2",
            command=self.create_person_entries,
            width=15,
            relief=tk.FLAT
        )
        self.submit_btn.grid(row=2, column=0, columnspan=2, pady=15)

        self.name_entries = []
        self.paid_entries = []
        self.result_text = None

    def _add_input_field(self, label_text, row):
        tk.Label(
            self.input_frame,
            text=label_text,
            font=("Segoe UI", 12),
            bg="#f0f4f8",
            fg="#34495e"
        ).grid(row=row, column=0, sticky="w", pady=5)

    def _add_entry_field(self, row):
        entry = tk.Entry(self.input_frame, font=("Segoe UI", 12), width=20)
        entry.grid(row=row, column=1, padx=10, pady=5)
        return entry

    def create_person_entries(self):
        try:
            self.total_people = int(self.people_entry.get())
            self.total_amount = float(self.amount_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers.")
            return

        self.people_entry.config(state="disabled")
        self.amount_entry.config(state="disabled")
        self.submit_btn.config(state="disabled")

        self.input_frame2 = tk.Frame(self.root, bg="#f0f4f8")
        self.input_frame2.pack(pady=10)

        for i in range(self.total_people):
            tk.Label(self.input_frame2, text=f"Name {i+1}:", font=("Segoe UI", 11), bg="#f0f4f8").grid(row=i, column=0, sticky="w", pady=4)
            name_entry = tk.Entry(self.input_frame2, font=("Segoe UI", 11), width=20)
            name_entry.grid(row=i, column=1, padx=8)

            tk.Label(self.input_frame2, text="Paid ₹:", font=("Segoe UI", 11), bg="#f0f4f8").grid(row=i, column=2, sticky="w")
            paid_entry = tk.Entry(self.input_frame2, font=("Segoe UI", 11), width=15)
            paid_entry.grid(row=i, column=3, padx=8)

            self.name_entries.append(name_entry)
            self.paid_entries.append(paid_entry)

        tk.Button(
            self.root,
            text="💡 Calculate",
            font=("Segoe UI", 12, "bold"),
            bg="#2980b9",
            fg="white",
            activebackground="#21618c",
            cursor="hand2",
            command=self.calculate_split,
            width=18,
            relief=tk.FLAT
        ).pack(pady=15)

        output_frame = tk.Frame(self.root, bg="#f0f4f8")
        output_frame.pack(pady=10)

        self.result_text = tk.Text(
            output_frame,
            height=15,
            width=80,
            font=("Consolas", 11),
            bg="white",
            fg="#2d3436",
            bd=2,
            relief=tk.GROOVE,
            wrap=tk.WORD
        )
        self.result_text.pack(side=tk.LEFT, fill=tk.BOTH)

        scroll = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.result_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_text.config(yscrollcommand=scroll.set)

    def calculate_split(self):
        names = []
        contributions = []

        try:
            for i in range(self.total_people):
                name = self.name_entries[i].get().strip()
                amount = float(self.paid_entries[i].get())
                if not name:
                    messagebox.showerror("Missing Name", f"Please enter a name for Person {i+1}")
                    return
                names.append(name)
                contributions.append(amount)
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numeric values for payment.")
            return

        equal_share = self.total_amount / self.total_people
        balances = [round(paid - equal_share, 2) for paid in contributions]

        creditors = [[i, bal] for i, bal in enumerate(balances) if bal > 0]
        debtors = [[i, -bal] for i, bal in enumerate(balances) if bal < 0]

        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, f"💰 Equal share per person: ₹{equal_share:.2f}\n\n")
        self.result_text.insert(tk.END, "📄 Summary:\n")
        for i in range(self.total_people):
            status = "receives" if balances[i] > 0 else "pays" if balances[i] < 0 else "is settled"
            self.result_text.insert(
                tk.END,
                f"• {names[i]} paid ₹{contributions[i]:.2f} → {status} ₹{abs(balances[i]):.2f}\n"
            )

        self.result_text.insert(tk.END, "\n🤝 Settlements:\n")
        i = j = 0
        while i < len(debtors) and j < len(creditors):
            d_idx, d_amt = debtors[i]
            c_idx, c_amt = creditors[j]
            pay_amt = min(d_amt, c_amt)
            self.result_text.insert(
                tk.END,
                f"→ {names[d_idx]} pays ₹{pay_amt:.2f} to {names[c_idx]}\n"
            )
            debtors[i][1] -= pay_amt
            creditors[j][1] -= pay_amt
            if debtors[i][1] == 0:
                i += 1
            if creditors[j][1] == 0:
                j += 1


# Launch the app
if __name__ == "__main__":
    root = tk.Tk()
    app = ExpenseSplitterApp(root)
    root.mainloop()
