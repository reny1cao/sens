#!/usr/bin/env python3
"""
Strategic Data Loader for SENS
Implements phased loading plan with progress tracking and rate limit management.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from sens.datasource.financial import FinancialDataLoader

logger = structlog.get_logger(__name__)

# Define all loading phases
LOADING_PHASES = {
    "1A": {
        "name": "Complete Current Securities",
        "type": "stocks",
        "symbols": ["CRM", "DIS", "HD", "JNJ", "NFLX", "PG", "V"],
        "description": "Complete the 15 securities already in database",
        "estimated_minutes": 90
    },
    "1B": {
        "name": "Market Indices & Benchmarks",
        "type": "stocks",
        "symbols": ["SPY", "QQQ", "DIA", "IWM", "VTI", "VOO"],
        "description": "Core market ETFs for benchmarking",
        "estimated_minutes": 75
    },
    "1C": {
        "name": "Sector ETFs",
        "type": "stocks",
        "symbols": ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLB", "XLRE", "XLU"],
        "description": "Complete sector coverage for analysis",
        "estimated_minutes": 120
    },
    "1D": {
        "name": "Critical Economic Indicators",
        "type": "economic",
        "indicators": ["VIXCLS", "DGS10", "DGS2", "DFF", "DEXUSEU", "INDPRO", 
                      "HOUST", "UMCSENT", "NAPM", "T10Y2Y", "BAMLH0A0HYM2"],
        "description": "Key market and economic indicators",
        "estimated_minutes": 30
    },
    "2A": {
        "name": "Technology Expansion",
        "type": "stocks",
        "symbols": ["ORCL", "CRM", "ADBE", "AMD", "INTC", "CSCO", "AVGO", "TXN", "QCOM"],
        "description": "Major tech companies beyond FAANG",
        "estimated_minutes": 110
    },
    "2B": {
        "name": "Healthcare Leaders",
        "type": "stocks",
        "symbols": ["UNH", "CVS", "LLY", "TMO", "ABT", "DHR", "BMY", "AMGN", "GILD"],
        "description": "Top healthcare and pharma companies",
        "estimated_minutes": 110
    },
    "2C": {
        "name": "Financial Services",
        "type": "stocks",
        "symbols": ["BRK.B", "WFC", "GS", "MS", "BLK", "SPGI", "AXP", "C", "USB"],
        "description": "Major banks and financial services",
        "estimated_minutes": 110
    },
    "2D": {
        "name": "Consumer & Retail",
        "type": "stocks",
        "symbols": ["WMT", "COST", "TGT", "SBUX", "NKE", "LOW", "TJX", "CMG"],
        "description": "Retail and consumer leaders",
        "estimated_minutes": 100
    },
    "2E": {
        "name": "Energy & Industrials",
        "type": "stocks",
        "symbols": ["XOM", "CVX", "COP", "SLB", "EOG", "BA", "HON", "UNP", "UPS"],
        "description": "Energy and industrial giants",
        "estimated_minutes": 110
    },
    "3A": {
        "name": "Growth & Innovation",
        "type": "stocks",
        "symbols": ["SNOW", "DDOG", "NET", "ZM", "ROKU", "SQ", "SHOP", "COIN", 
                   "RIVN", "LCID", "PLTR", "U", "RBLX", "ABNB"],
        "description": "High-growth and emerging tech leaders",
        "estimated_minutes": 170
    },
    "4A": {
        "name": "International & Commodities",
        "type": "stocks",
        "symbols": ["TSM", "BABA", "NVO", "ASML", "SAP", "GLD", "SLV", "USO", "UNG", "DBA"],
        "description": "International stocks and commodity ETFs",
        "estimated_minutes": 120
    }
}

PROGRESS_FILE = Path(__file__).parent / "loading_progress.json"


class ProgressTracker:
    """Track loading progress across phases."""
    
    def __init__(self):
        self.progress = self._load_progress()
    
    def _load_progress(self) -> Dict[str, Any]:
        """Load progress from file."""
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        return {
            "phases_completed": [],
            "symbols_loaded": [],
            "indicators_loaded": [],
            "last_updated": None,
            "total_records": 0
        }
    
    def save_progress(self):
        """Save progress to file."""
        self.progress["last_updated"] = datetime.now().isoformat()
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def mark_phase_complete(self, phase_id: str, records_loaded: int):
        """Mark a phase as complete."""
        if phase_id not in self.progress["phases_completed"]:
            self.progress["phases_completed"].append(phase_id)
        self.progress["total_records"] += records_loaded
        self.save_progress()
    
    def add_symbols(self, symbols: List[str]):
        """Add loaded symbols."""
        for symbol in symbols:
            if symbol not in self.progress["symbols_loaded"]:
                self.progress["symbols_loaded"].append(symbol)
        self.save_progress()
    
    def add_indicators(self, indicators: List[str]):
        """Add loaded indicators."""
        for indicator in indicators:
            if indicator not in self.progress["indicators_loaded"]:
                self.progress["indicators_loaded"].append(indicator)
        self.save_progress()
    
    def is_phase_complete(self, phase_id: str) -> bool:
        """Check if phase is already complete."""
        return phase_id in self.progress["phases_completed"]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get progress summary."""
        return {
            "phases_completed": len(self.progress["phases_completed"]),
            "total_phases": len(LOADING_PHASES),
            "symbols_loaded": len(self.progress["symbols_loaded"]),
            "indicators_loaded": len(self.progress["indicators_loaded"]),
            "total_records": self.progress["total_records"],
            "last_updated": self.progress["last_updated"]
        }


async def load_phase(phase_id: str, tracker: ProgressTracker, skip_if_complete: bool = True):
    """Load a specific phase with progress tracking."""
    
    phase = LOADING_PHASES.get(phase_id)
    if not phase:
        print(f"❌ Invalid phase ID: {phase_id}")
        return
    
    # Check if already complete
    if skip_if_complete and tracker.is_phase_complete(phase_id):
        print(f"✓ Phase {phase_id} already complete, skipping...")
        return
    
    print(f"\n{'='*70}")
    print(f"📊 Phase {phase_id}: {phase['name']}")
    print(f"📝 {phase['description']}")
    print(f"⏱️  Estimated time: {phase['estimated_minutes']} minutes")
    print('='*70)
    
    start_time = datetime.now()
    
    try:
        async with FinancialDataLoader() as loader:
            if phase["type"] == "stocks":
                # Load stock data
                symbols = phase.get("symbols", [])
                print(f"\nLoading {len(symbols)} symbols: {', '.join(symbols)}")
                
                # Load securities info first
                print("\n1️⃣ Loading company information...")
                for i, symbol in enumerate(symbols):
                    try:
                        print(f"   [{i+1}/{len(symbols)}] {symbol}...", end='', flush=True)
                        await loader.load_securities_info([symbol])
                        print(" ✓")
                        await asyncio.sleep(12)  # Rate limit
                    except Exception as e:
                        print(f" ✗ Error: {str(e)}")
                
                # Load price data
                print("\n2️⃣ Loading price data...")
                response = await loader.load_daily_prices_batch(symbols, use_csv=True)
                
                if response.success:
                    print(f"✅ Loaded {response.records_loaded} price records")
                    tracker.add_symbols(response.symbols_processed)
                    tracker.mark_phase_complete(phase_id, response.records_loaded)
                else:
                    print(f"❌ Failed: {response.message}")
                    for error in response.errors[:5]:
                        print(f"   - {error}")
                        
            elif phase["type"] == "economic":
                # Load economic indicators
                indicators = phase.get("indicators", [])
                print(f"\nLoading {len(indicators)} economic indicators")
                
                start_date = datetime.now().date() - timedelta(days=730)  # 2 years
                response = await loader.load_economic_indicators(
                    indicators, start_date, datetime.now().date()
                )
                
                if response.success:
                    print(f"✅ Loaded {response.records_loaded} indicator records")
                    tracker.add_indicators(response.symbols_processed)
                    tracker.mark_phase_complete(phase_id, response.records_loaded)
                else:
                    print(f"❌ Failed: {response.message}")
                    
    except Exception as e:
        print(f"\n❌ Phase failed with error: {str(e)}")
        logger.error("phase_loading_error", phase_id=phase_id, error=str(e))
    
    elapsed = (datetime.now() - start_time).total_seconds() / 60
    print(f"\n⏱️  Phase completed in {elapsed:.1f} minutes")
    
    # Show progress
    summary = tracker.get_summary()
    print(f"\n📈 Overall Progress: {summary['phases_completed']}/{summary['total_phases']} phases")
    print(f"   Symbols loaded: {summary['symbols_loaded']}")
    print(f"   Total records: {summary['total_records']:,}")


async def run_all_phases(start_phase: str = None, end_phase: str = None):
    """Run all phases or a range of phases."""
    
    tracker = ProgressTracker()
    phase_ids = list(LOADING_PHASES.keys())
    
    # Determine range
    if start_phase:
        try:
            start_idx = phase_ids.index(start_phase)
        except ValueError:
            print(f"❌ Invalid start phase: {start_phase}")
            return
    else:
        start_idx = 0
    
    if end_phase:
        try:
            end_idx = phase_ids.index(end_phase) + 1
        except ValueError:
            print(f"❌ Invalid end phase: {end_phase}")
            return
    else:
        end_idx = len(phase_ids)
    
    phases_to_run = phase_ids[start_idx:end_idx]
    
    print("🚀 STRATEGIC DATA LOADING PLAN")
    print(f"📋 Phases to run: {', '.join(phases_to_run)}")
    print(f"⏱️  Total estimated time: {sum(LOADING_PHASES[p]['estimated_minutes'] for p in phases_to_run)} minutes")
    
    # Confirm
    response = input("\nProceed with loading? (y/n): ")
    if response.lower() != 'y':
        print("❌ Loading cancelled")
        return
    
    # Run phases
    for phase_id in phases_to_run:
        await load_phase(phase_id, tracker)
        
        # Wait between phases to avoid overwhelming the API
        if phase_id != phases_to_run[-1]:
            print("\n⏸️  Waiting 60 seconds before next phase...")
            await asyncio.sleep(60)
    
    # Final summary
    print("\n" + "="*70)
    print("✅ LOADING COMPLETE")
    summary = tracker.get_summary()
    print(f"📊 Final Statistics:")
    print(f"   Phases completed: {summary['phases_completed']}/{summary['total_phases']}")
    print(f"   Symbols loaded: {summary['symbols_loaded']}")
    print(f"   Indicators loaded: {summary['indicators_loaded']}")
    print(f"   Total records: {summary['total_records']:,}")
    print("="*70)


async def show_status():
    """Show current loading status."""
    tracker = ProgressTracker()
    summary = tracker.get_summary()
    
    print("\n📊 STRATEGIC LOADING STATUS")
    print("="*50)
    print(f"Phases completed: {summary['phases_completed']}/{summary['total_phases']}")
    print(f"Symbols loaded: {summary['symbols_loaded']}")
    print(f"Indicators loaded: {summary['indicators_loaded']}")
    print(f"Total records: {summary['total_records']:,}")
    print(f"Last updated: {summary['last_updated'] or 'Never'}")
    
    print("\n✅ Completed phases:")
    for phase_id in tracker.progress["phases_completed"]:
        phase = LOADING_PHASES.get(phase_id, {})
        print(f"   {phase_id}: {phase.get('name', 'Unknown')}")
    
    print("\n⏳ Remaining phases:")
    for phase_id, phase in LOADING_PHASES.items():
        if phase_id not in tracker.progress["phases_completed"]:
            print(f"   {phase_id}: {phase['name']} (~{phase['estimated_minutes']} min)")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Strategic Data Loader for SENS")
    parser.add_argument("command", choices=["run", "status", "phase"], 
                       help="Command to execute")
    parser.add_argument("--phase", help="Specific phase to run (e.g., 1A)")
    parser.add_argument("--start", help="Start phase for range")
    parser.add_argument("--end", help="End phase for range")
    parser.add_argument("--force", action="store_true", 
                       help="Force re-run even if phase is complete")
    
    args = parser.parse_args()
    
    if args.command == "status":
        asyncio.run(show_status())
    elif args.command == "phase":
        if not args.phase:
            print("❌ Must specify --phase for phase command")
            sys.exit(1)
        tracker = ProgressTracker()
        asyncio.run(load_phase(args.phase, tracker, skip_if_complete=not args.force))
    elif args.command == "run":
        asyncio.run(run_all_phases(args.start, args.end))


if __name__ == "__main__":
    main()