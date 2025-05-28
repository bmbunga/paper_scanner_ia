def add_pro_user(email):
    with open("pro_users.txt", "a", encoding="utf-8") as f:
        f.write(email + "\n")
