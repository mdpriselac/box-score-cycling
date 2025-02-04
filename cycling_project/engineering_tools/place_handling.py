#The basic idea of our place buckets is to look at how the UCI assigns points to finishing positions and then create buckets where there are big shifts in total point allocations. We're not going to follow this precisely but we're going to approximate it to reflect the basic idea. there are big changes in point gaps with the Winner compared to Podium, podium compared to top 5, top 5 compared to top 8, top 8 compared to top 15, top 15 compared to 30, and top 30 compared to top 50. We're also going to add a DNF. Our points buckets are as follows:
# 0:Winner
# 1:Podium
# 2:Top 5
# 3:Top 10 (here we make a change from the uci to reflect the idea that top 10 is a bit more natural in terms of thinkign about an out come or performacne than 8)
# 4:Top 15
# 5:Top 30
# 6:Outside top 30
# 7:DNF/OTL/DNS (yes, DNS is not a DNF but we're going to treat it as such for simplicity)

def place_bucketer(place:int|str)->int:
    if place is None:
        #print("Place is None for this rider, returning None, check data")
        return None
    if isinstance(place,str):
        try:
            place = int(place.strip())
        except:
            #print(f"Place is a string that can't be converted to an int: {place}")
            return 7
    if isinstance(place, int):
        if place == 1:
            return 0
        elif place <= 3:
            return 1
        elif place <= 5:
            return 2
        elif place <= 10:
            return 3
        elif place <= 15:
            return 4
        elif place <= 30:
            return 5
        else:
            return 6

