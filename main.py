import pandas as pd
from spotdl import Spotdl
from pydub import AudioSegment
import librosa
import numpy as np
import os
import tempfile

class FastSongProcessor:
    def __init__(self):
        # Initialize spotdl
        self.spot = Spotdl(
            client_id="1e7160661b5849e7a50f41de5b8f9ef1",  # You'll need to get these from Spotify Developer Dashboard
            client_secret="6c04a0251cda402688b667a8a4df52ec"
        )
        self.temp_dir = tempfile.mkdtemp()
    
    def download_song(self, song_name, artist):
        """
        Download song using spotdl - much faster than youtube-dl
        """
        try:
            search_query = f"{song_name} {artist}"
            print(f"Searching for: {search_query}")
            
            # Search for the song
            songs = self.spot.search([search_query])
            if not songs:
                print(f"Could not find {search_query}")
                return None
            
            # Download the first match
            song = songs[0]
            temp_path = os.path.join(self.temp_dir, f"{song.name}.mp3")
            
            # Download and convert to AudioSegment
            self.spot.download(song, temp_path)
            audio = AudioSegment.from_mp3(temp_path)
            
            # Clean up temp file
            os.remove(temp_path)
            
            return audio
            
        except Exception as e:
            print(f"Error downloading {song_name}: {e}")
            return None

    def detect_chorus(self, audio_segment, min_chorus_length=10000):
        """
        Detect chorus in audio using librosa
        Returns timestamp of likely chorus start
        """
        # Convert AudioSegment to numpy array
        samples = np.array(audio_segment.get_array_of_samples())
        
        # Convert to mono if stereo
        if audio_segment.channels == 2:
            samples = samples.reshape((-1, 2)).mean(axis=1)
        
        # Normalize samples
        samples = samples.astype(float) / np.max(np.abs(samples))
        
        # Compute chromagram
        chroma = librosa.feature.chroma_cqt(
            y=samples,
            sr=audio_segment.frame_rate,
            hop_length=512
        )
        
        # Compute similarity matrix
        sim_matrix = librosa.segment.recurrence_matrix(
            chroma,
            mode='similarity',
            width=5
        )
        
        # Find repeated sections (potential chorus)
        chorus_frames = librosa.segment.detect_repeating(sim_matrix)
        
        if len(chorus_frames) > 0:
            # Convert frames to milliseconds
            chorus_start = librosa.frames_to_time(
                chorus_frames[0],
                sr=audio_segment.frame_rate
            ) * 1000
            
            # Ensure chorus is not too close to the start
            if chorus_start < min_chorus_length:
                chorus_start = min_chorus_length
                
            return chorus_start
            
        return None

    def extract_chorus(self, audio_segment, start_ms, duration_ms=30000):
        """
        Extract chorus segment from audio
        """
        try:
            end_ms = start_ms + duration_ms
            # Ensure we don't exceed audio length
            if end_ms > len(audio_segment):
                end_ms = len(audio_segment)
            
            # Fade in/out to make transitions smoother
            chorus = audio_segment[start_ms:end_ms]
            chorus = chorus.fade_in(100).fade_out(100)
            
            return chorus
        except Exception as e:
            print(f"Error extracting chorus: {e}")
            return None

def mix_segments(segments, crossfade_duration=1000):
    """
    Mix audio segments with crossfade
    """
    if not segments:
        return None
    
    final_mix = segments[0]
    position = len(final_mix)
    
    for segment in segments[1:]:
        # Apply crossfade
        final_mix = final_mix.overlay(
            segment,
            position=position - crossfade_duration
        )
        position = len(final_mix)
    
    # Normalize volume
    final_mix = final_mix.normalize()
    return final_mix

def main():
    # Read song list
    try:
        df = pd.read_excel('ed_sheeran_songs.xlsx')
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return

    processor = FastSongProcessor()
    chorus_segments = []
    
    for _, row in df.iterrows():
        song_name = row['song_name']
        artist = row['artist']
        
        print(f"\nProcessing: {song_name} by {artist}")
        
        # Download audio
        audio = processor.download_song(song_name, artist)
        if audio is None:
            continue
        
        # Detect and extract chorus
        chorus_start = processor.detect_chorus(audio)
        if chorus_start is not None:
            chorus = processor.extract_chorus(audio, chorus_start)
            if chorus is not None:
                chorus_segments.append(chorus)
                print(f"✓ Successfully extracted chorus from {song_name}")
        
        print(f"Progress: {len(chorus_segments)}/{len(df)} songs processed")

    # Mix choruses together
    if chorus_segments:
        print("\nMixing choruses...")
        final_mix = mix_segments(chorus_segments)
        final_mix.export("ed_sheeran_chorus_mix.wav", format="wav")
        print("✓ Successfully created chorus mix!")
        print("Output saved as: ed_sheeran_chorus_mix.wav")

if __name__ == "__main__":
    main()