# ==============================================================================
# F1 MCP SERVER - CLAUDE DESKTOP VERSION
# ==============================================================================
# Purpose: MCP server for Claude Desktop integration
# Image Output: Returns ImageContent objects for direct display in Claude
# Usage: Configure in Claude Desktop's MCP settings
# ==============================================================================

from fastmcp import FastMCP
from mcp.types import ImageContent
import fastf1
import fastf1.plotting
import fastf1.livetiming
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import requests
import io
import base64
import os
from datetime import datetime

# PREVENT CRASHES: Use 'Agg' backend (no GUI window needed)
matplotlib.use('Agg')

# Initialize Server
mcp = FastMCP("F1 Mega Engineer")

# Setup caching
# 1. Get the folder where THIS script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Create the full path to the cache folder
cache_dir = os.path.join(script_dir, 'cache')

# 3. Create the directory manually if it doesn't exist
os.makedirs(cache_dir, exist_ok=True)

# 4. Enable cache with the FULL path
fastf1.Cache.enable_cache(cache_dir)

# ==============================================================================
# MODULE 1: CALENDAR & SESSIONS
# ==============================================================================

@mcp.tool()
def get_schedule(year: int) -> str:
    """Get the full race calendar for a specific year (excluding testing)."""
    try:
        schedule = fastf1.get_event_schedule(year)
        races = schedule[schedule['EventFormat'] != 'testing']
        return races[['RoundNumber', 'EventDate', 'Country', 'Location', 'EventName']].to_string(index=False)
    except Exception as e:
        return f"Error fetching schedule: {e}"

@mcp.tool()
def get_session_info(year: int, gp: str, session: str = 'R') -> str:
    """Get start time and status of a specific session (R=Race, Q=Quali, FP1, etc)."""
    try:
        s = fastf1.get_session(year, gp, session)
        return f"Session: {s.name}\nDate: {s.date}\nCircuit: {s.event.Location}\nStatus: {s.event.EventName}"
    except Exception as e:
        return f"Error: {e}"

# ==============================================================================
# MODULE 2: RACE RESULTS & LAPS
# ==============================================================================

@mcp.tool()
def get_race_results(year: int, gp: str) -> str:
    """Get the final classification (Position, Driver, Team, Points)."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load(telemetry=False, weather=False)
        res = session.results[['ClassifiedPosition', 'Abbreviation', 'TeamName', 'Time', 'Points']]
        return res.to_string(index=False)
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def get_fastest_lap_data(year: int, gp: str, driver: str, session: str = 'Q') -> str:
    """Get detailed stats for a driver's fastest lap (Sector times, Speed trap)."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(telemetry=False)
        lap = s.laps.pick_driver(driver).pick_fastest()
        
        return f"""
        🚗 Driver: {driver}
        ⏱️ Time: {str(lap['LapTime']).split('days')[-1]}
        🟣 Sector 1: {lap['Sector1Time'].total_seconds()}s
        🟣 Sector 2: {lap['Sector2Time'].total_seconds()}s
        🟣 Sector 3: {lap['Sector3Time'].total_seconds()}s
        🚀 Speed Trap: {lap['SpeedST']} km/h
        🛞 Tyre: {lap['Compound']} ({lap['TyreLife']} laps old)
        """
    except Exception as e:
        return f"Error: {e}"

# ==============================================================================
# MODULE 3: TELEMETRY & PHYSICS (VISUAL)
# ==============================================================================

@mcp.tool()
def plot_telemetry_comparison(year: int, gp: str, driver1: str, driver2: str, session: str = 'Q') -> ImageContent:
    """
    Generates a Speed Trace comparison image between two drivers.
    Returns: An ImageContent object that can be displayed in the client.
    """
    try:
        s = fastf1.get_session(year, gp, session)
        s.load()

        d1 = s.laps.pick_driver(driver1).pick_fastest()
        d2 = s.laps.pick_driver(driver2).pick_fastest()
        
        t1 = d1.get_car_data().add_distance()
        t2 = d2.get_car_data().add_distance()

        fastf1.plotting.setup_mpl()
        fig, ax = plt.subplots(figsize=(10, 5))
        
        ax.plot(t1['Distance'], t1['Speed'], color='blue', label=driver1)
        ax.plot(t2['Distance'], t2['Speed'], color='orange', label=driver2)
        ax.set_ylabel('Speed (km/h)')
        ax.set_xlabel('Distance (m)')
        ax.legend()
        plt.title(f"{driver1} vs {driver2} - Speed Trace")

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return ImageContent(type="image", data=img_base64, mimeType="image/png")
    except Exception as e:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, f"Error: {str(e)}", 
                ha='center', va='center', fontsize=12, color='red')
        ax.axis('off')
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        
        return ImageContent(type="image",data=img_base64, mimeType="image/png")
        #return f"Plot Error: {e}"

@mcp.tool()
def plot_gear_shifts(year: int, gp: str, driver: str, session: str = 'Q') -> ImageContent:
    """Generates a Gear Shift chart for a single driver."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load()
        
        # Get the driver's laps
        driver_laps = s.laps.pick_driver(driver)
        if driver_laps.empty:
            raise ValueError(f"No laps found for driver {driver}")
        
        # Pick the fastest lap
        lap = driver_laps.pick_fastest()
        if lap is None or lap.empty:
            raise ValueError(f"No valid fastest lap found for {driver}")
        
        # Get telemetry data
        tel = lap.get_telemetry().add_distance()
        if tel is None or tel.empty:
            raise ValueError(f"No telemetry data available for {driver}")

        fastf1.plotting.setup_mpl()
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(tel['Distance'], tel['nGear'], label='Gear', color='green')
        ax.set_ylabel('Gear')
        ax.set_xlabel('Distance (m)')
        plt.title(f"{driver} Gear Usage - {gp} {year}")
        ax.legend()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        
        return ImageContent(
            type="image",
            data=img_base64,
            mimeType="image/png"
        )
    except Exception as e:
        # Create an error image instead of returning a string
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, f"Error: {str(e)}", 
                ha='center', va='center', fontsize=12, color='red', wrap=True)
        ax.axis('off')
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        
        return ImageContent(
            type="image",
            data=img_base64,
            mimeType="image/png"
        )

# ==============================================================================
# MODULE 4: WEATHER & TRACK CONDITIONS
# ==============================================================================

@mcp.tool()
def get_weather_data(year: int, gp: str, session: str = 'R') -> str:
    """Get detailed weather conditions (Rain, Track Temp, Wind)."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(laps=False, weather=True)
        w = s.weather_data
        
        return f"""
        🌡️ Average Air Temp: {w['AirTemp'].mean():.1f}°C
        🔥 Average Track Temp: {w['TrackTemp'].mean():.1f}°C
        💧 Humidity: {w['Humidity'].mean():.1f}%
        🌧️ Rain Detected: {w['Rainfall'].any()}
        💨 Wind Speed: {w['WindSpeed'].mean():.1f} m/s
        """
    except Exception as e:
        return f"Weather Error: {e}"

@mcp.tool()
def get_circuit_info(year: int, gp: str) -> str:
    """Get track layout info (Corners, DRS Zones)."""
    try:
        s = fastf1.get_session(year, gp, 'Q')
        s.load(laps=True, telemetry=True) # Telemetry needed for circuit info
        info = s.get_circuit_info()
        
        corners = info.corners[['Number', 'Letter', 'Angle', 'Distance']].to_string(index=False)
        return f"Circuit Rotation: {info.rotation} degrees\n\nCorners:\n{corners}"
    except Exception as e:
        return f"Circuit Info Error: {e}"

# ==============================================================================
# MODULE 5: TYRE STRATEGY
# ==============================================================================

@mcp.tool()
def get_tyre_strategy(year: int, gp: str, driver: str) -> str:
    """List all tyre compounds used and stint lengths."""
    try:
        s = fastf1.get_session(year, gp, 'R')
        s.load()
        laps = s.laps.pick_driver(driver)
        
        stints = laps.groupby('Stint').agg({
            'Compound': 'first',
            'LapNumber': ['min', 'max'],
            'TyreLife': 'max'
        })
        return f"Tyre Strategy for {driver}:\n{stints.to_string()}"
    except Exception as e:
        return f"Strategy Error: {e}"

# ==============================================================================
# MODULE 6: AUDIO & TEAM RADIO
# ==============================================================================

@mcp.tool()
def get_team_radio(year: int, gp: str, driver_number: int) -> str:
    """Get audio links for team radio (Uses OpenF1 API)."""
    try:
        # Fetch Session Key
        url_s = f"https://api.openf1.org/v1/sessions?year={year}&country_name={gp}&session_name=Race"
        s_data = requests.get(url_s).json()
        if not s_data: return "Session not found in OpenF1."
        session_key = s_data[0]['session_key']

        # Fetch Radio
        url_r = f"https://api.openf1.org/v1/team_radio?session_key={session_key}&driver_number={driver_number}"
        r_data = requests.get(url_r).json()
        
        transcript = f"📻 Last 5 Radio Messages (Driver #{driver_number}):\n"
        for msg in r_data[-5:]:
            transcript += f"- {msg['recording_url']}\n"
        return transcript
    except Exception as e:
        return f"Radio Error: {e}"

# ==============================================================================
# MODULE 7: PIT STOPS & STRATEGY
# ==============================================================================

@mcp.tool()
def get_pit_stops(year: int, gp: str, driver: str = None) -> str:
    """Get pit stop data for all drivers or a specific driver in a race."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load()
        
        if driver:
            laps = session.laps.pick_drivers(driver)
        else:
            laps = session.laps
        
        # Get pit laps (laps where pit stop occurred)
        pit_laps = laps[laps['PitInTime'].notna()]
        
        if len(pit_laps) == 0:
            return "No pit stops found"
        
        result = "🔧 Pit Stops:\n"
        for idx, lap in pit_laps.iterrows():
            pit_time = (lap['PitOutTime'] - lap['PitInTime']).total_seconds()
            result += f"Lap {int(lap['LapNumber'])}: {lap['Driver']} - {pit_time:.1f}s ({lap['Compound']})\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 8: STANDINGS & POINTS
# ==============================================================================

@mcp.tool()
def get_driver_standings(year: int, round_number: int = None) -> str:
    """Get driver championship standings after a specific round or latest."""
    try:
        if round_number:
            url = f"http://ergast.com/api/f1/{year}/{round_number}/driverStandings.json"
        else:
            url = f"http://ergast.com/api/f1/{year}/driverStandings.json"
        
        response = requests.get(url)
        data = response.json()
        standings = data['MRData']['StandingsTable']['StandingsLists'][0]['DriverStandings']
        
        result = f"🏆 Driver Standings {year}"
        if round_number:
            result += f" (After Round {round_number})"
        result += ":\n\n"
        
        for driver in standings[:10]:
            pos = driver['position']
            name = f"{driver['Driver']['givenName']} {driver['Driver']['familyName']}"
            points = driver['points']
            team = driver['Constructors'][0]['name']
            result += f"{pos}. {name} ({team}) - {points} pts\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_constructor_standings(year: int, round_number: int = None) -> str:
    """Get constructor/team championship standings."""
    try:
        if round_number:
            url = f"http://ergast.com/api/f1/{year}/{round_number}/constructorStandings.json"
        else:
            url = f"http://ergast.com/api/f1/{year}/constructorStandings.json"
        
        response = requests.get(url)
        data = response.json()
        standings = data['MRData']['StandingsTable']['StandingsLists'][0]['ConstructorStandings']
        
        result = f"🏆 Constructor Standings {year}"
        if round_number:
            result += f" (After Round {round_number})"
        result += ":\n\n"
        
        for team in standings:
            pos = team['position']
            name = team['Constructor']['name']
            points = team['points']
            result += f"{pos}. {name} - {points} pts\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 9: SPRINT RACES
# ==============================================================================

@mcp.tool()
def get_sprint_results(year: int, gp: str) -> str:
    """Get sprint race results (for sprint weekends)."""
    try:
        session = fastf1.get_session(year, gp, 'S')
        session.load(telemetry=False, weather=False)
        
        res = session.results[['ClassifiedPosition', 'Abbreviation', 'TeamName', 'Time', 'Points']]
        return f"🏁 Sprint Results - {gp} {year}:\n{res.to_string(index=False)}"
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 10: SECTOR & LAP ANALYSIS
# ==============================================================================

@mcp.tool()
def compare_sector_times(year: int, gp: str, driver1: str, driver2: str, session: str = 'Q') -> str:
    """Compare sector times between two drivers."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(telemetry=False)
        
        lap1 = s.laps.pick_drivers(driver1).pick_fastest()
        lap2 = s.laps.pick_drivers(driver2).pick_fastest()
        
        result = f"⏱️ Sector Comparison - {driver1} vs {driver2}:\n\n"
        
        sectors = ['Sector1Time', 'Sector2Time', 'Sector3Time']
        for i, sector in enumerate(sectors, 1):
            time1 = lap1[sector].total_seconds()
            time2 = lap2[sector].total_seconds()
            diff = time1 - time2
            faster = driver1 if diff < 0 else driver2
            result += f"Sector {i}: {time1:.3f}s vs {time2:.3f}s (Δ {abs(diff):.3f}s, {faster} faster)\n"
        
        total1 = lap1['LapTime'].total_seconds()
        total2 = lap2['LapTime'].total_seconds()
        diff_total = total1 - total2
        faster_total = driver1 if diff_total < 0 else driver2
        result += f"\nTotal: {total1:.3f}s vs {total2:.3f}s (Δ {abs(diff_total):.3f}s, {faster_total} faster)"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_lap_times(year: int, gp: str, driver: str, session: str = 'R') -> str:
    """Get all lap times for a driver in a session."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(telemetry=False)
        
        laps = s.laps.pick_drivers(driver)
        
        result = f"⏱️ Lap Times - {driver} ({gp} {year} {session}):\n\n"
        for idx, lap in laps.iterrows():
            lap_num = int(lap['LapNumber'])
            lap_time = str(lap['LapTime']).split('days')[-1].strip() if pd.notna(lap['LapTime']) else 'N/A'
            compound = lap['Compound'] if pd.notna(lap['Compound']) else 'N/A'
            deleted = " [DELETED]" if lap.get('Deleted', False) else ""
            result += f"Lap {lap_num}: {lap_time} ({compound}){deleted}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 11: DELETED LAPS & TRACK LIMITS
# ==============================================================================

@mcp.tool()
def get_deleted_laps(year: int, gp: str, session: str = 'Q') -> str:
    """Get all laps deleted due to track limits or other violations."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(messages=True)
        
        deleted_laps = s.laps[s.laps['Deleted'] == True]
        
        if len(deleted_laps) == 0:
            return "No deleted laps found"
        
        result = f"🚫 Deleted Laps - {gp} {year} {session}:\n\n"
        for idx, lap in deleted_laps.iterrows():
            driver = lap['Driver']
            lap_num = int(lap['LapNumber'])
            lap_time = str(lap['LapTime']).split('days')[-1].strip()
            reason = lap['DeletedReason'] if pd.notna(lap['DeletedReason']) else 'Unknown'
            result += f"{driver} - Lap {lap_num} ({lap_time}): {reason}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 12: RACE PACE & POSITION CHANGES
# ==============================================================================

@mcp.tool()
def get_position_changes(year: int, gp: str, driver: str) -> str:
    """Track position changes throughout the race for a driver."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load()
        
        laps = session.laps.pick_drivers(driver)
        
        result = f"📊 Position Changes - {driver} ({gp} {year}):\n\n"
        result += f"Starting Position: {int(laps.iloc[0]['Position'])}\n"
        result += f"Finishing Position: {int(laps.iloc[-1]['Position'])}\n\n"
        
        result += "Lap-by-lap positions:\n"
        for idx, lap in laps.iterrows():
            if pd.notna(lap['Position']):
                result += f"Lap {int(lap['LapNumber'])}: P{int(lap['Position'])}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 13: TRACK STATUS & RACE CONTROL
# ==============================================================================

@mcp.tool()
def get_track_status(year: int, gp: str, session: str = 'R') -> str:
    """Get track status changes (yellow flags, safety car, red flag, etc.)."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load()
        
        track_status = s.track_status
        
        result = f"🚦 Track Status Changes - {gp} {year} {session}:\n\n"
        
        # Track status meanings
        status_map = {
            '1': '🟢 All Clear',
            '2': '🟡 Yellow Flag',
            '3': '🟢 Green Flag',
            '4': '🔴 Safety Car',
            '5': '🔴 Red Flag',
            '6': '🟡 Virtual Safety Car',
            '7': '🟢 VSC Ending'
        }
        
        for idx, row in track_status.iterrows():
            status = row['Status']
            time = row['Time']
            status_text = status_map.get(status, f'Status {status}')
            result += f"{time}: {status_text}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_race_control_messages(year: int, gp: str, session: str = 'R') -> str:
    """Get all race control messages during a session."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(messages=True)
        
        messages = s.race_control_messages
        
        if len(messages) == 0:
            return "No race control messages found"
        
        result = f"📢 Race Control Messages - {gp} {year} {session}:\n\n"
        
        for idx, msg in messages.iterrows():
            time = msg['Time']
            category = msg['Category']
            message = msg['Message']
            result += f"[{time}] {category}: {message}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 14: DRIVER & TEAM INFO
# ==============================================================================

@mcp.tool()
def get_driver_info(year: int, gp: str, driver: str) -> str:
    """Get detailed driver information (number, team, headshot, etc.)."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load(telemetry=False)
        
        driver_result = session.get_driver(driver)
        
        result = f"👤 Driver Info - {driver}:\n\n"
        result += f"Full Name: {driver_result['FullName']}\n"
        result += f"Number: {driver_result['DriverNumber']}\n"
        result += f"Team: {driver_result['TeamName']}\n"
        result += f"Country: {driver_result['CountryCode']}\n"
        result += f"Abbreviation: {driver_result['Abbreviation']}\n"
        
        if pd.notna(driver_result.get('HeadshotUrl')):
            result += f"Headshot: {driver_result['HeadshotUrl']}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_team_laps(year: int, gp: str, team: str, session: str = 'R') -> str:
    """Get all laps for a specific team (both drivers)."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(telemetry=False)
        
        team_laps = s.laps.pick_teams(team)
        
        drivers = pd.unique(team_laps['Driver'])
        
        result = f"🏎️ Team Laps - {team} ({gp} {year} {session}):\n\n"
        
        for driver in drivers:
            driver_laps = team_laps[team_laps['Driver'] == driver]
            fastest = driver_laps.pick_fastest()
            avg_time = driver_laps['LapTime'].mean()
            
            result += f"{driver}:\n"
            result += f"  Laps: {len(driver_laps)}\n"
            result += f"  Fastest: {str(fastest['LapTime']).split('days')[-1].strip()}\n"
            result += f"  Average: {str(avg_time).split('days')[-1].strip()}\n\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 15: SPEED TRAP & DRS
# ==============================================================================

@mcp.tool()
def get_speed_trap_comparison(year: int, gp: str, session: str = 'Q') -> str:
    """Compare speed trap data across all drivers."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(telemetry=False)
        
        # Get fastest lap per driver
        drivers = pd.unique(s.laps['Driver'])
        speed_data = []
        
        for drv in drivers:
            fastest = s.laps.pick_drivers(drv).pick_fastest()
            if pd.notna(fastest['SpeedST']):
                speed_data.append({
                    'Driver': drv,
                    'Team': fastest['Team'],
                    'Speed': fastest['SpeedST']
                })
        
        # Sort by speed
        speed_df = pd.DataFrame(speed_data).sort_values('Speed', ascending=False)
        
        result = f"🚀 Speed Trap Comparison - {gp} {year} {session}:\n\n"
        for i, row in speed_df.iterrows():
            result += f"{row['Driver']} ({row['Team']}): {row['Speed']:.1f} km/h\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def analyze_drs_usage(year: int, gp: str, driver: str, session: str = 'Q') -> str:
    """Analyze DRS usage patterns for a driver's fastest lap."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load()
        
        lap = s.laps.pick_drivers(driver).pick_fastest()
        tel = lap.get_car_data()
        
        # Count DRS activations (DRS values: 0=Off, 1-14=DRS levels)
        drs_active = tel[tel['DRS'] > 0]
        drs_percentage = (len(drs_active) / len(tel)) * 100 if len(tel) > 0 else 0
        
        result = f"💨 DRS Analysis - {driver} ({gp} {year}):\n\n"
        result += f"DRS Active: {drs_percentage:.1f}% of lap\n"
        result += f"DRS Samples: {len(drs_active)} / {len(tel)}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 16: COMPOUND & TIRE ANALYSIS
# ==============================================================================

@mcp.tool()
def compare_tire_compounds(year: int, gp: str, session: str = 'R') -> str:
    """Compare average lap times across different tire compounds."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(telemetry=False)
        
        # Filter for accurate laps only
        laps = s.laps.pick_accurate()
        
        compounds = pd.unique(laps['Compound'])
        
        result = f"🛞 Tire Compound Comparison - {gp} {year}:\n\n"
        
        for compound in compounds:
            if pd.notna(compound):
                compound_laps = laps.pick_compounds(compound)
                avg_time = compound_laps['LapTime'].mean()
                fastest_time = compound_laps['LapTime'].min()
                result += f"{compound}:\n"
                result += f"  Average: {str(avg_time).split('days')[-1].strip()}\n"
                result += f"  Fastest: {str(fastest_time).split('days')[-1].strip()}\n"
                result += f"  Laps: {len(compound_laps)}\n\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_stint_analysis(year: int, gp: str, driver: str) -> str:
    """Analyze each stint: compound, lap times, degradation."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load()
        
        laps = session.laps.pick_drivers(driver)
        
        result = f"📊 Stint Analysis - {driver} ({gp} {year}):\n\n"
        
        stints = laps.groupby('Stint')
        
        for stint_num, stint_laps in stints:
            compound = stint_laps.iloc[0]['Compound']
            start_lap = int(stint_laps.iloc[0]['LapNumber'])
            end_lap = int(stint_laps.iloc[-1]['LapNumber'])
            num_laps = len(stint_laps)
            
            # Calculate average pace
            avg_time = stint_laps['LapTime'].mean()
            
            result += f"Stint {int(stint_num)}: {compound}\n"
            result += f"  Laps {start_lap}-{end_lap} ({num_laps} laps)\n"
            result += f"  Avg Time: {str(avg_time).split('days')[-1].strip()}\n\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 17: DNF & RETIREMENTS
# ==============================================================================

@mcp.tool()
def get_dnf_list(year: int, gp: str) -> str:
    """Get list of drivers who did not finish the race and reasons."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load(telemetry=False)
        
        results = session.results
        
        # Filter for DNFs (Status not 'Finished')
        dnfs = results[results['Status'] != 'Finished']
        
        if len(dnfs) == 0:
            return "All drivers finished the race!"
        
        result = f"⚠️ DNF/Retirements - {gp} {year}:\n\n"
        
        for idx, driver in dnfs.iterrows():
            name = driver['Abbreviation']
            team = driver['TeamName']
            status = driver['Status']
            result += f"{name} ({team}): {status}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 18: FASTEST SECTORS
# ==============================================================================

@mcp.tool()
def get_fastest_sectors(year: int, gp: str, session: str = 'Q') -> str:
    """Find who set the fastest time in each sector."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(telemetry=False)
        
        drivers = pd.unique(s.laps['Driver'])
        
        # Get fastest lap per driver
        fastest_laps = []
        for drv in drivers:
            lap = s.laps.pick_drivers(drv).pick_fastest()
            fastest_laps.append(lap)
        
        from fastf1.core import Laps
        all_fastest = Laps(fastest_laps)
        
        result = f"⚡ Fastest Sectors - {gp} {year} {session}:\n\n"
        
        for i in [1, 2, 3]:
            sector_col = f'Sector{i}Time'
            fastest_sector = all_fastest.sort_values(sector_col).iloc[0]
            driver = fastest_sector['Driver']
            time = fastest_sector[sector_col].total_seconds()
            result += f"Sector {i}: {driver} - {time:.3f}s\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 19: GRID VS FINISH
# ==============================================================================

@mcp.tool()
def compare_grid_to_finish(year: int, gp: str) -> str:
    """Compare starting grid positions to finishing positions."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load(telemetry=False)
        
        results = session.results
        
        result = f"🏁 Grid vs Finish - {gp} {year}:\n\n"
        
        for idx, driver in results.iterrows():
            name = driver['Abbreviation']
            grid = int(driver['GridPosition']) if pd.notna(driver['GridPosition']) else 'N/A'
            finish = driver['ClassifiedPosition']
            
            if grid != 'N/A' and finish != 'R':
                try:
                    finish_int = int(finish)
                    change = grid - finish_int
                    change_str = f"+{change}" if change > 0 else str(change)
                    result += f"{name}: P{grid} → P{finish} ({change_str})\n"
                except:
                    result += f"{name}: P{grid} → {finish}\n"
            else:
                result += f"{name}: P{grid} → {finish}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 20: QUALIFYING SESSIONS (Q1, Q2, Q3)
# ==============================================================================

@mcp.tool()
def get_qualifying_progression(year: int, gp: str) -> str:
    """Show who was eliminated in Q1, Q2 and who made it to Q3."""
    try:
        session = fastf1.get_session(year, gp, 'Q')
        session.load()
        
        q1, q2, q3 = session.laps.split_qualifying_sessions()
        
        result = f"🏁 Qualifying Progression - {gp} {year}:\n\n"
        
        # Q3 participants
        if q3 is not None:
            q3_drivers = pd.unique(q3['Driver'])
            result += f"Q3 (Top 10): {', '.join(q3_drivers)}\n\n"
        
        # Q2 eliminated
        if q2 is not None:
            q2_drivers = pd.unique(q2['Driver'])
            if q3 is not None:
                eliminated_q2 = [d for d in q2_drivers if d not in q3_drivers]
                result += f"Eliminated in Q2 (P11-15): {', '.join(eliminated_q2)}\n\n"
        
        # Q1 eliminated
        if q1 is not None:
            q1_drivers = pd.unique(q1['Driver'])
            if q2 is not None:
                eliminated_q1 = [d for d in q1_drivers if d not in q2_drivers]
                result += f"Eliminated in Q1 (P16-20): {', '.join(eliminated_q1)}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 21: LAP CONSISTENCY & STATISTICS
# ==============================================================================

@mcp.tool()
def analyze_lap_consistency(year: int, gp: str, driver: str, session: str = 'R') -> str:
    """Analyze lap time consistency (standard deviation, variation)."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(telemetry=False)
        
        laps = s.laps.pick_drivers(driver).pick_accurate()
        
        if len(laps) == 0:
            return "No accurate laps found for analysis"
        
        lap_times = laps['LapTime'].dt.total_seconds()
        
        avg = lap_times.mean()
        fastest = lap_times.min()
        slowest = lap_times.max()
        std_dev = lap_times.std()
        
        result = f"📊 Lap Consistency - {driver} ({gp} {year} {session}):\n\n"
        result += f"Average: {avg:.3f}s\n"
        result += f"Fastest: {fastest:.3f}s\n"
        result += f"Slowest: {slowest:.3f}s\n"
        result += f"Std Dev: {std_dev:.3f}s\n"
        result += f"Range: {slowest - fastest:.3f}s\n"
        result += f"Total Laps: {len(laps)}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 22: BRAKE & THROTTLE ANALYSIS
# ==============================================================================

@mcp.tool()
def analyze_brake_points(year: int, gp: str, driver: str, session: str = 'Q') -> str:
    """Analyze braking patterns on fastest lap."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load()
        
        lap = s.laps.pick_drivers(driver).pick_fastest()
        tel = lap.get_car_data()
        
        # Brake is boolean: True when braking
        brake_points = tel[tel['Brake'] == True]
        total_brake_time = len(brake_points) / len(tel) * 100 if len(tel) > 0 else 0
        
        # Throttle percentage
        avg_throttle = tel['Throttle'].mean()
        max_throttle = tel['Throttle'].max()
        full_throttle = len(tel[tel['Throttle'] >= 99]) / len(tel) * 100 if len(tel) > 0 else 0
        
        result = f"🚦 Brake & Throttle Analysis - {driver} ({gp} {year}):\n\n"
        result += f"Braking: {total_brake_time:.1f}% of lap\n"
        result += f"Brake Events: {len(brake_points)} samples\n\n"
        result += f"Avg Throttle: {avg_throttle:.1f}%\n"
        result += f"Full Throttle: {full_throttle:.1f}% of lap\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 23: RPM & ENGINE ANALYSIS
# ==============================================================================

@mcp.tool()
def analyze_rpm_data(year: int, gp: str, driver: str, session: str = 'Q') -> str:
    """Analyze engine RPM patterns on fastest lap."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load()
        
        lap = s.laps.pick_drivers(driver).pick_fastest()
        tel = lap.get_car_data()
        
        avg_rpm = tel['RPM'].mean()
        max_rpm = tel['RPM'].max()
        min_rpm = tel['RPM'].min()
        
        result = f"🔧 RPM Analysis - {driver} ({gp} {year}):\n\n"
        result += f"Average RPM: {avg_rpm:.0f}\n"
        result += f"Max RPM: {max_rpm:.0f}\n"
        result += f"Min RPM: {min_rpm:.0f}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 24: FASTEST PIT STOPS
# ==============================================================================

@mcp.tool()
def get_fastest_pit_stops(year: int, gp: str, top_n: int = 10) -> str:
    """Get the fastest pit stops of the race."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load()
        
        laps = session.laps
        pit_laps = laps[laps['PitInTime'].notna()].copy()
        
        if len(pit_laps) == 0:
            return "No pit stops found"
        
        # Calculate pit stop duration
        pit_laps['PitDuration'] = (pit_laps['PitOutTime'] - pit_laps['PitInTime']).dt.total_seconds()
        
        # Sort by duration
        fastest_stops = pit_laps.nsmallest(top_n, 'PitDuration')
        
        result = f"⚡ Top {top_n} Fastest Pit Stops - {gp} {year}:\n\n"
        
        for i, (idx, lap) in enumerate(fastest_stops.iterrows(), 1):
            driver = lap['Driver']
            duration = lap['PitDuration']
            lap_num = int(lap['LapNumber'])
            result += f"{i}. {driver} - Lap {lap_num}: {duration:.2f}s\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 25: FRESH VS USED TIRES
# ==============================================================================

@mcp.tool()
def compare_tire_age_performance(year: int, gp: str, driver: str) -> str:
    """Compare lap times on fresh vs used tires."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load()
        
        laps = session.laps.pick_drivers(driver).pick_accurate()
        
        fresh_laps = laps[laps['FreshTyre'] == True]
        used_laps = laps[laps['FreshTyre'] == False]
        
        result = f"🛞 Tire Age Performance - {driver} ({gp} {year}):\n\n"
        
        if len(fresh_laps) > 0:
            fresh_avg = fresh_laps['LapTime'].mean()
            result += f"Fresh Tires:\n"
            result += f"  Laps: {len(fresh_laps)}\n"
            result += f"  Avg Time: {str(fresh_avg).split('days')[-1].strip()}\n\n"
        
        if len(used_laps) > 0:
            used_avg = used_laps['LapTime'].mean()
            result += f"Used Tires:\n"
            result += f"  Laps: {len(used_laps)}\n"
            result += f"  Avg Time: {str(used_avg).split('days')[-1].strip()}\n\n"
        
        if len(fresh_laps) > 0 and len(used_laps) > 0:
            delta = (used_avg - fresh_avg).total_seconds()
            result += f"Difference: {delta:.3f}s (used tires slower)"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 26: PENALTIES & INVESTIGATIONS
# ==============================================================================

@mcp.tool()
def get_penalties(year: int, gp: str) -> str:
    """Get all penalties issued during the race."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load(messages=True)
        
        messages = session.race_control_messages
        
        # Filter for penalty-related messages
        penalties = messages[messages['Message'].str.contains('PENALTY|penalty|time|grid', case=False, na=False)]
        
        if len(penalties) == 0:
            return "No penalties issued"
        
        result = f"⚖️ Penalties - {gp} {year}:\n\n"
        
        for idx, msg in penalties.iterrows():
            time = msg['Time']
            message = msg['Message']
            result += f"[{time}] {message}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 27: HISTORICAL WINNERS (ERGAST API)
# ==============================================================================

@mcp.tool()
def get_race_winners_history(gp: str, years: int = 5) -> str:
    """Get race winners for a specific GP over the last N years."""
    try:
        current_year = 2025
        start_year = current_year - years + 1
        
        result = f"🏆 Race Winners History - {gp} (Last {years} years):\n\n"
        
        for year in range(current_year, start_year - 1, -1):
            try:
                url = f"http://ergast.com/api/f1/{year}/circuits.json"
                response = requests.get(url)
                circuits = response.json()['MRData']['CircuitTable']['Circuits']
                
                # Find circuit
                circuit_id = None
                for circuit in circuits:
                    if gp.lower() in circuit['circuitName'].lower() or gp.lower() in circuit['Location']['locality'].lower():
                        circuit_id = circuit['circuitId']
                        break
                
                if not circuit_id:
                    continue
                
                # Get results
                url = f"http://ergast.com/api/f1/{year}/circuits/{circuit_id}/results/1.json"
                response = requests.get(url)
                data = response.json()
                
                if data['MRData']['RaceTable']['Races']:
                    race = data['MRData']['RaceTable']['Races'][0]
                    winner = race['Results'][0]
                    driver_name = f"{winner['Driver']['givenName']} {winner['Driver']['familyName']}"
                    team = winner['Constructor']['name']
                    result += f"{year}: {driver_name} ({team})\n"
            except:
                continue
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 28: OVERTAKES DETECTION
# ==============================================================================

@mcp.tool()
def detect_overtakes(year: int, gp: str, driver: str) -> str:
    """Detect when a driver overtook others (position gained between laps)."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load()
        
        laps = session.laps.pick_drivers(driver)
        
        result = f"🏁 Overtakes - {driver} ({gp} {year}):\n\n"
        
        overtakes = []
        for i in range(1, len(laps)):
            prev_pos = laps.iloc[i-1]['Position']
            curr_pos = laps.iloc[i]['Position']
            
            if pd.notna(prev_pos) and pd.notna(curr_pos):
                if curr_pos < prev_pos:  # Position improved (lower number = better)
                    lap_num = int(laps.iloc[i]['LapNumber'])
                    positions_gained = int(prev_pos - curr_pos)
                    overtakes.append((lap_num, prev_pos, curr_pos, positions_gained))
        
        if len(overtakes) == 0:
            return f"{driver} did not gain positions during the race"
        
        total_gained = sum(o[3] for o in overtakes)
        result += f"Total Positions Gained: {total_gained}\n\n"
        
        for lap, old_pos, new_pos, gained in overtakes:
            result += f"Lap {lap}: P{int(old_pos)} → P{int(new_pos)} (+{gained})\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 29: GAP ANALYSIS
# ==============================================================================

@mcp.tool()
def get_gap_to_leader(year: int, gp: str, driver: str) -> str:
    """Track gap to race leader throughout the race."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load()
        
        driver_laps = session.laps.pick_drivers(driver)
        all_laps = session.laps
        
        result = f"⏱️ Gap to Leader - {driver} ({gp} {year}):\n\n"
        
        for idx, lap in driver_laps.iterrows():
            lap_num = int(lap['LapNumber'])
            
            # Find leader at same lap
            same_lap = all_laps[all_laps['LapNumber'] == lap_num]
            leader_lap = same_lap[same_lap['Position'] == 1.0]
            
            if len(leader_lap) > 0 and pd.notna(lap['Time']) and pd.notna(leader_lap.iloc[0]['Time']):
                gap = (lap['Time'] - leader_lap.iloc[0]['Time']).total_seconds()
                result += f"Lap {lap_num}: +{gap:.3f}s\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 30: LONG RUN PACE (PRACTICE SESSIONS)
# ==============================================================================

@mcp.tool()
def analyze_long_run_pace(year: int, gp: str, driver: str, session: str = 'FP2') -> str:
    """Analyze race simulation pace from practice sessions."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(telemetry=False)
        
        laps = s.laps.pick_drivers(driver)
        
        # Filter for consecutive laps (race sim)
        long_runs = []
        current_run = []
        
        for idx, lap in laps.iterrows():
            if pd.notna(lap['LapTime']) and not lap.get('PitInTime'):
                current_run.append(lap)
            else:
                if len(current_run) >= 5:  # At least 5 consecutive laps
                    long_runs.append(current_run)
                current_run = []
        
        if len(current_run) >= 5:
            long_runs.append(current_run)
        
        if len(long_runs) == 0:
            return "No long runs found (need 5+ consecutive laps)"
        
        result = f"🏃 Long Run Pace - {driver} ({gp} {year} {session}):\n\n"
        
        for i, run in enumerate(long_runs, 1):
            lap_times = [lap['LapTime'] for lap in run]
            avg_time = pd.Series(lap_times).mean()
            compound = run[0]['Compound']
            
            result += f"Run {i} ({compound}):\n"
            result += f"  Laps: {len(run)}\n"
            result += f"  Avg Time: {str(avg_time).split('days')[-1].strip()}\n\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 31: HEAD-TO-HEAD COMPARISON
# ==============================================================================

@mcp.tool()
def team_head_to_head(year: int, gp: str, team: str, session: str = 'Q') -> str:
    """Compare both drivers in a team head-to-head."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(telemetry=False)
        
        team_laps = s.laps.pick_teams(team)
        drivers = pd.unique(team_laps['Driver'])
        
        if len(drivers) != 2:
            return "Could not find exactly 2 drivers for this team"
        
        d1, d2 = drivers[0], drivers[1]
        
        d1_fastest = team_laps.pick_drivers(d1).pick_fastest()
        d2_fastest = team_laps.pick_drivers(d2).pick_fastest()
        
        result = f"⚔️ Head-to-Head - {team} ({gp} {year} {session}):\n\n"
        
        # Lap times
        d1_time = d1_fastest['LapTime'].total_seconds()
        d2_time = d2_fastest['LapTime'].total_seconds()
        delta = abs(d1_time - d2_time)
        faster = d1 if d1_time < d2_time else d2
        
        result += f"{d1}: {d1_time:.3f}s\n"
        result += f"{d2}: {d2_time:.3f}s\n"
        result += f"\nFaster: {faster} by {delta:.3f}s\n\n"
        
        # Sector comparison
        result += "Sector Comparison:\n"
        for i in [1, 2, 3]:
            sector = f'Sector{i}Time'
            s1 = d1_fastest[sector].total_seconds()
            s2 = d2_fastest[sector].total_seconds()
            faster_s = d1 if s1 < s2 else d2
            result += f"S{i}: {faster_s} by {abs(s1-s2):.3f}s\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 32: TRACK RECORDS
# ==============================================================================

@mcp.tool()
def get_track_record(gp: str) -> str:
    """Get the all-time lap record for a specific circuit (via Ergast)."""
    try:
        # This would need to query multiple years to find the fastest
        # For now, we'll get recent fastest lap from last completed season
        year = 2024
        
        url = f"http://ergast.com/api/f1/{year}/circuits.json"
        response = requests.get(url)
        circuits = response.json()['MRData']['CircuitTable']['Circuits']
        
        circuit_id = None
        for circuit in circuits:
            if gp.lower() in circuit['circuitName'].lower() or gp.lower() in circuit['Location']['locality'].lower():
                circuit_id = circuit['circuitId']
                circuit_name = circuit['circuitName']
                break
        
        if not circuit_id:
            return f"Circuit '{gp}' not found"
        
        # Get fastest lap
        url = f"http://ergast.com/api/f1/{year}/circuits/{circuit_id}/fastest/1/results.json"
        response = requests.get(url)
        data = response.json()
        
        if data['MRData']['RaceTable']['Races']:
            race = data['MRData']['RaceTable']['Races'][0]
            fastest = race['Results'][0]
            driver = f"{fastest['Driver']['givenName']} {fastest['Driver']['familyName']}"
            time = fastest['FastestLap']['Time']['time']
            
            result = f"🏁 Track Record - {circuit_name}:\n\n"
            result += f"Driver: {driver}\n"
            result += f"Time: {time}\n"
            result += f"Year: {year}\n"
            
            return result
        
        return "Track record data not available"
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 33: SESSION SUMMARY
# ==============================================================================

@mcp.tool()
def get_session_summary(year: int, gp: str, session: str = 'R') -> str:
    """Get a comprehensive quick summary of a session."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load()
        
        result = f"📋 Session Summary - {gp} {year} {session}:\n\n"
        
        # Basic info
        result += f"Date: {s.date}\n"
        result += f"Circuit: {s.event.Location}, {s.event.Country}\n\n"
        
        # Winner or pole
        if session in ['R', 'S']:
            winner = s.results.iloc[0]
            result += f"Winner: {winner['Abbreviation']} ({winner['TeamName']})\n"
            if pd.notna(winner['Time']):
                result += f"Time: {winner['Time']}\n"
        elif session in ['Q', 'SQ', 'SS']:
            pole = s.results.iloc[0]
            result += f"Pole: {pole['Abbreviation']} ({pole['TeamName']})\n"
            if 'Q3' in pole and pd.notna(pole['Q3']):
                result += f"Time: {pole['Q3']}\n"
        
        result += f"\nTotal Laps: {len(s.laps)}\n"
        result += f"Drivers: {len(s.drivers)}\n"
        
        # Weather summary
        if hasattr(s, 'weather_data') and s.weather_data is not None:
            w = s.weather_data
            result += f"\nWeather:\n"
            result += f"  Air Temp: {w['AirTemp'].mean():.1f}°C\n"
            result += f"  Track Temp: {w['TrackTemp'].mean():.1f}°C\n"
            result += f"  Rainfall: {w['Rainfall'].any()}\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 34: TIRE STRATEGY COMPARISON
# ==============================================================================

@mcp.tool()
def compare_strategies(year: int, gp: str, driver1: str, driver2: str) -> str:
    """Compare tire strategies between two drivers."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load()
        
        d1_laps = session.laps.pick_drivers(driver1)
        d2_laps = session.laps.pick_drivers(driver2)
        
        result = f"📊 Strategy Comparison - {driver1} vs {driver2} ({gp} {year}):\n\n"
        
        # Driver 1 stints
        result += f"{driver1}:\n"
        for stint in d1_laps.groupby('Stint'):
            stint_num = stint[0]
            stint_laps = stint[1]
            compound = stint_laps.iloc[0]['Compound']
            start = int(stint_laps.iloc[0]['LapNumber'])
            end = int(stint_laps.iloc[-1]['LapNumber'])
            result += f"  Stint {int(stint_num)}: {compound} (Laps {start}-{end})\n"
        
        result += f"\n{driver2}:\n"
        for stint in d2_laps.groupby('Stint'):
            stint_num = stint[0]
            stint_laps = stint[1]
            compound = stint_laps.iloc[0]['Compound']
            start = int(stint_laps.iloc[0]['LapNumber'])
            end = int(stint_laps.iloc[-1]['LapNumber'])
            result += f"  Stint {int(stint_num)}: {compound} (Laps {start}-{end})\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 35: STARTING TIRE ANALYSIS
# ==============================================================================

@mcp.tool()
def analyze_starting_tires(year: int, gp: str) -> str:
    """Analyze which tire compounds were used at race start."""
    try:
        session = fastf1.get_session(year, gp, 'R')
        session.load()
        
        # Get first lap for each driver
        first_laps = session.laps[session.laps['LapNumber'] == 1]
        
        result = f"🏁 Starting Tire Choices - {gp} {year}:\n\n"
        
        # Group by compound
        for compound in pd.unique(first_laps['Compound']):
            if pd.notna(compound):
                drivers = first_laps[first_laps['Compound'] == compound]['Driver'].tolist()
                result += f"{compound}: {', '.join(drivers)}\n"
        
        # Count by compound
        result += "\nSummary:\n"
        compound_counts = first_laps['Compound'].value_counts()
        for compound, count in compound_counts.items():
            if pd.notna(compound):
                result += f"  {compound}: {count} drivers\n"
        
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MODULE 36: BEST PERSONAL LAPS
# ==============================================================================

@mcp.tool()
def get_personal_best_laps(year: int, gp: str, session: str = 'Q') -> str:
    """Get each driver's personal best lap time."""
    try:
        s = fastf1.get_session(year, gp, session)
        s.load(telemetry=False)
        
        # Get personal best laps (IsPersonalBest flag)
        pb_laps = s.laps[s.laps['IsPersonalBest'] == True]
        pb_laps = pb_laps.sort_values('LapTime')
        
        result = f"⭐ Personal Best Laps - {gp} {year} {session}:\n\n"
        
        for idx, lap in pb_laps.iterrows():
            driver = lap['Driver']
            team = lap['Team']
            time = str(lap['LapTime']).split('days')[-1].strip()
            result += f"{driver} ({team}): {time}\n"
        
        return result
    except Exception as e:
        return f"Error: {e}"

# ==============================================================================
# MODULE 28: LIVE TIMING (Real-time Race Data)
# ==============================================================================

@mcp.tool()
def get_live_session_status() -> str:
    """Get current live F1 session status and timing information."""
    try:
        # Connect to live timing
        livedata = fastf1.livetiming.LiveTimingData()
        
        result = "🔴 LIVE F1 Session Status:\n\n"
        
        # Get session info
        if hasattr(livedata, 'session_info'):
            info = livedata.session_info
            result += f"Session: {info.get('Name', 'Unknown')}\n"
            result += f"Track: {info.get('Meeting', {}).get('Circuit', 'Unknown')}\n"
            result += f"Status: {info.get('Status', 'Unknown')}\n\n"
        
        return result
    except Exception as e:
        return f"No live session active or error: {e}"

@mcp.tool()
def get_live_positions() -> str:
    """Get current live race positions and gaps."""
    try:
        livedata = fastf1.livetiming.LiveTimingData()
        
        result = "🏁 LIVE Race Positions:\n\n"
        
        # Get position data
        if hasattr(livedata, 'position_data'):
            positions = livedata.position_data
            
            for pos, driver_data in sorted(positions.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
                driver = driver_data.get('Driver', 'Unknown')
                gap = driver_data.get('GapToLeader', '0.0')
                interval = driver_data.get('IntervalToPositionAhead', '')
                
                result += f"P{pos}: {driver}"
                if gap != '0.0':
                    result += f" +{gap}s"
                if interval:
                    result += f" (Δ {interval})"
                result += "\n"
        
        return result
    except Exception as e:
        return f"No live session active or error: {e}"

@mcp.tool()
def get_live_lap_times() -> str:
    """Get latest lap times from live session."""
    try:
        livedata = fastf1.livetiming.LiveTimingData()
        
        result = "⏱️ LIVE Lap Times:\n\n"
        
        # Get timing data
        if hasattr(livedata, 'timing_data'):
            timing = livedata.timing_data
            
            for driver_num, driver_data in timing.items():
                driver = driver_data.get('Driver', f'#{driver_num}')
                last_lap = driver_data.get('LastLapTime', {})
                
                if last_lap:
                    lap_time = last_lap.get('Value', 'N/A')
                    personal_best = driver_data.get('BestLapTime', {}).get('Value', 'N/A')
                    
                    result += f"{driver}: {lap_time}"
                    if personal_best != 'N/A':
                        result += f" (PB: {personal_best})"
                    result += "\n"
        
        return result
    except Exception as e:
        return f"No live session active or error: {e}"

@mcp.tool()
def get_live_sector_times(driver: str) -> str:
    """Get live sector times for a specific driver."""
    try:
        livedata = fastf1.livetiming.LiveTimingData()
        
        result = f"🟣 LIVE Sector Times - {driver}:\n\n"
        
        # Find driver in timing data
        if hasattr(livedata, 'timing_data'):
            timing = livedata.timing_data
            
            driver_data = None
            for num, data in timing.items():
                if data.get('Driver', '').upper() == driver.upper():
                    driver_data = data
                    break
            
            if driver_data:
                sectors = driver_data.get('Sectors', [])
                for i, sector in enumerate(sectors, 1):
                    sector_time = sector.get('Value', 'N/A')
                    personal_best = sector.get('PersonalFastest', False)
                    overall_best = sector.get('OverallFastest', False)
                    
                    result += f"Sector {i}: {sector_time}"
                    if personal_best:
                        result += " 🟢 (PB)"
                    if overall_best:
                        result += " 🟣 (Fastest)"
                    result += "\n"
            else:
                result += f"Driver {driver} not found in live timing"
        
        return result
    except Exception as e:
        return f"No live session active or error: {e}"

@mcp.tool()
def get_live_telemetry(driver: str) -> str:
    """Get live telemetry data for a specific driver (speed, throttle, etc)."""
    try:
        livedata = fastf1.livetiming.LiveTimingData()
        
        result = f"📊 LIVE Telemetry - {driver}:\n\n"
        
        # Get car data from live timing
        if hasattr(livedata, 'car_data'):
            car_data = livedata.car_data
            
            driver_data = None
            for num, data in car_data.items():
                if data.get('Driver', '').upper() == driver.upper():
                    driver_data = data
                    break
            
            if driver_data:
                result += f"Speed: {driver_data.get('Speed', 'N/A')} km/h\n"
                result += f"Gear: {driver_data.get('Gear', 'N/A')}\n"
                result += f"RPM: {driver_data.get('RPM', 'N/A')}\n"
                result += f"Throttle: {driver_data.get('Throttle', 'N/A')}%\n"
                result += f"Brake: {driver_data.get('Brake', 'N/A')}\n"
                result += f"DRS: {driver_data.get('DRS', 'N/A')}\n"
            else:
                result += f"Driver {driver} not found in live telemetry"
        
        return result
    except Exception as e:
        return f"No live session active or error: {e}"

@mcp.tool()
def get_live_weather() -> str:
    """Get current live weather conditions at the track."""
    try:
        livedata = fastf1.livetiming.LiveTimingData()
        
        result = "🌤️ LIVE Weather Conditions:\n\n"
        
        # Get weather data
        if hasattr(livedata, 'weather_data'):
            weather = livedata.weather_data
            
            result += f"Air Temp: {weather.get('AirTemp', 'N/A')}°C\n"
            result += f"Track Temp: {weather.get('TrackTemp', 'N/A')}°C\n"
            result += f"Humidity: {weather.get('Humidity', 'N/A')}%\n"
            result += f"Pressure: {weather.get('Pressure', 'N/A')} mbar\n"
            result += f"Wind Speed: {weather.get('WindSpeed', 'N/A')} m/s\n"
            result += f"Wind Direction: {weather.get('WindDirection', 'N/A')}°\n"
            result += f"Rainfall: {weather.get('Rainfall', 'N/A')}\n"
        
        return result
    except Exception as e:
        return f"No live session active or error: {e}"
    except Exception as e:
        return f"Error: {str(e)}"

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    print("🏎️  F1 Mega Server Running...")
    mcp.run()