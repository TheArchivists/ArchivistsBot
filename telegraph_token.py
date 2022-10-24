from telegraph import Telegraph

telegraph = Telegraph()
telegraph.create_account(short_name=input("Enter a username for your graph.org : "))

print(f"Your graph.org token ==>  {telegraph.get_access_token()}")