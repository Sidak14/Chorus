import pandas as pd

# Create a list of Ed Sheeran's famous songs with their titles
songs_data = {
    'song_name': [
        'Shape of You',
        'Perfect',
        'Thinking Out Loud',
        'Photograph',
        'Castle on the Hill',
        'Bad Habits',
        'Shivers',
        'Eyes Closed',
        'The A Team',
        'Don\'t'
    ],
    'artist': ['Ed Sheeran'] * 10  # All songs are by Ed Sheeran
}

# Create DataFrame
df = pd.DataFrame(songs_data)

# Save to Excel file
df.to_excel('ed_sheeran_songs.xlsx', index=False)

print("Spreadsheet created successfully!")