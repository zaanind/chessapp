import random
import string
from datetime import datetime
import calendar

def generate_fake_game_info():
    """Generate a random list of fake games and bet summary for a bot."""
    
    # Random game list 0–20
    game_count = random.randint(0, 20)
    game_list = []
    
    now = datetime.now()
    year = now.year
    month = now.month
    max_day = calendar.monthrange(year, month)[1]
    
    for _ in range(game_count):
        # Random capital letter game name, 4–10 letters
        name_length = random.randint(4, 10)
        game_name = ''.join(random.choices(string.ascii_uppercase, k=name_length))
        
        # Random bet amount 1–100
        bet_amount = round(random.uniform(1, 100), 2)
        
        # Random result
        result = random.choice(['won', 'lost'])
        
        # Random date in current month
        day = random.randint(1, max_day)
        hour = random.randint(0, 23)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        game_date = datetime(year, month, day, hour, minute, second).isoformat()
        
        game_list.append({
            "game_name": game_name,
            "bet_amount": bet_amount,
            "result": result,
            "date": game_date
        })
    
    # Random bets summary: around 50 ± 25
    total_bets = max(0, random.randint(25, 75))
    bets_won = max(0, random.randint(0, total_bets))
    
    return {
        "games": game_list,
        "bets": {
            "total_placed": total_bets,
            "won": bets_won
        }
    }

# Example usage
#fake_info = generate_fake_game_info()
#print(fake_info)
