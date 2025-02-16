# -*- coding: utf-8 -*-
"""
Created on Sat Jan  4 20:28:02 2025

@author: Edward Papiev
"""
import requests as rq
import pandas as pd
import numpy as np
from itertools import combinations
from datetime import datetime
stake = 100

api_key = '9126553aa7a47dbdae115638e9c52c1a'
base_url = 'https://api.the-odds-api.com/v4/sports'



#basic odds fetcher helper function
def pullodds(sport='upcoming', odds_format='decimal'):
    url = f'{base_url}/{sport}/odds'
    params = {
        'apiKey': api_key,
        'bookmakers':'betmgm,fanduel,draftkings,sport888,betway,betvictor,casumo',
        'market': 'h2h,totals',
        'oddsFormat': odds_format,
    }
    response = rq.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}, {response.json()}")
        return None
    
def normalize_data(odds_data):

    bookmakers_df = pd.json_normalize(
        odds_data,
        record_path='bookmakers',
        meta=['id', 'sport_key', 'sport_title', 'commence_time', 'home_team', 'away_team'],
        record_prefix='bookmaker_'
    )

    
    markets_df = pd.json_normalize(
        bookmakers_df.to_dict(orient='records'),
        record_path='bookmaker_markets',
        meta=['bookmaker_key', 'bookmaker_title', 'bookmaker_last_update', 'id', 'sport_key', 'sport_title', 'commence_time', 'home_team', 'away_team'],
        record_prefix='market_'
    )

    return markets_df    

def calculate_arbitrage(df):
    """
    Calculates arbitrage opportunities from the normalized odds data.
    """
    arbitrage_opportunities = []
    unique_ids = df['id'].unique()

    for id in unique_ids:
        subset = df[df['id'] == id]
        all_outcomes = []
        for index,row in subset.iterrows():
            outcomes_lists = row['market_outcomes']
            for outcome in outcomes_lists:
                outcome['book'] = row['bookmaker_title']
                outcome['sport'] = row['sport_title']
                d1 = datetime.fromisoformat(row['commence_time'])
                readable_date = d1.strftime("%B %d, %Y at %I:%M %p")
                outcome['date'] = readable_date
                
                all_outcomes.append(outcome)  # Append each list of dictionaries directly

        for comb in combinations(all_outcomes, 2):
            
            inv_odds_sum = sum(1 / float(outcome['price']) for outcome in comb)
            if inv_odds_sum < 1:
                arbitrage_opportunity = {
                    'id': id,
                    'sport': comb[0]['sport'],
                    'time': comb[0]['date'],
                    'book1': comb[0]['book'],
                    'team1': comb[0]['name'],
                    'odds1': comb[0]['price'],
                    'book2': comb[1]['book'],
                    'team2': comb[1]['name'],
                    'odds2': comb[1]['price'],
                    'inv_odds_sum': inv_odds_sum
                }
                arbitrage_opportunities.append(arbitrage_opportunity)
    arb = pd.DataFrame(arbitrage_opportunities)
    cleaned_arb = arb[arb['team1'] != arb['team2']]
    cleaned_arb['profit_margin'] = (1 - cleaned_arb['inv_odds_sum'])*100
    final_arb = cleaned_arb.sort_values(by = 'profit_margin', ascending  = False)
    
    return final_arb

def calc_all(df):
    allocations = []
    for index,row in df.iterrows():
        allocation = {
            'sport': row['sport'],
            'time': row['time'],
            'team1': row['team1'],
            'book1': row['book1'],
            'odds1': row['odds1'],
            'allocation1': ((1/float(row['odds1'])/(float(row['inv_odds_sum']))) * stake),
            'team2': row['team2'],
            'book2': row['book2'],
            'odds2': row['odds2'],
            'allocation2': ((1/float(row['odds2'])/(float(row['inv_odds_sum']))) * stake),
            'ROI': row['profit_margin']
        }
        allocations.append(allocation)
    alloc = pd.DataFrame(allocations)
    alloc['total_allocation'] = alloc['allocation1'] + alloc['allocation2']
    alloc['payout1'] = alloc['odds1'] * alloc['allocation1']
    alloc['payout2'] = alloc['odds2'] * alloc['allocation2']
    return alloc

if __name__ == "__main__":

    complete_data = pullodds()
    flat_data = pd.DataFrame(normalize_data(complete_data))
        
    filtered_df = flat_data[flat_data['market_outcomes'].apply(lambda x: len(x) == 2)]
    arbitrage_df = calculate_arbitrage(filtered_df)
    alloc_df = calc_all(arbitrage_df)
    
    print(alloc_df.to_markdown(index=False))
