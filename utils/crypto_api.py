"""
Crypto API utility functions for fetching funding rates and market data
Follows DRY principles by centralizing all API logic in one place
"""
import aiohttp
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger('discord-bot.crypto_api')

class CryptoAPI:
    """
    Centralized API client for cryptocurrency data
    Handles all interactions with the crypto API endpoints
    """
    
    def __init__(self, api_base_url: str, session: Optional[aiohttp.ClientSession] = None):
        """
        Initialize the crypto API client
        
        Args:
            api_base_url: Base URL for the API (e.g., 'https://example.com/api')
            session: Optional aiohttp session to reuse
        """
        self.api_base_url = api_base_url
        self.session = session
        self._owns_session = False
        
    async def ensure_session(self):
        """Ensure we have an active session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            self._owns_session = True
            
    async def close(self):
        """Close the session if we own it"""
        if self._owns_session and self.session:
            await self.session.close()
            self.session = None
            
    async def fetch_json(self, url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """
        Fetch JSON data from a URL
        
        Args:
            url: URL to fetch from
            timeout: Request timeout in seconds
            
        Returns:
            Parsed JSON data or None if failed
        """
        await self.ensure_session()
        
        try:
            async with self.session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"API request failed with status {response.status}: {url}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None
    
    # ========== Funding Rate Methods ==========
    
    async def get_most_negative_rates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get coins with the most negative funding rates
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of rate data dictionaries
        """
        data = await self.fetch_json(f"{self.api_base_url}/most-negative")
        if data and 'rates' in data:
            return data['rates'][:limit]
        return []
    
    async def get_turned_positive_rates(self, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Get coins that recently turned from negative to positive funding
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of rate data dictionaries
        """
        data = await self.fetch_json(f"{self.api_base_url}/turned-positive")
        if data and 'rates' in data:
            return data['rates'][:limit]
        return []
    
    async def get_improving_negative_rates(self, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Get negative rates that are improving (becoming less negative)
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of rate data dictionaries
        """
        data = await self.fetch_json(f"{self.api_base_url}/improving-negative")
        if data and 'rates' in data:
            return data['rates'][:limit]
        return []
    
    async def get_worsening_negative_rates(self, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Get negative rates that are worsening (becoming more negative)
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of rate data dictionaries
        """
        data = await self.fetch_json(f"{self.api_base_url}/worsening-negative")
        if data and 'rates' in data:
            return data['rates'][:limit]
        return []
    
    async def get_funding_scanner_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get comprehensive funding scanner data from all endpoints
        
        Returns:
            Dictionary with keys: most_negative, turned_positive, improving, worsening
        """
        endpoints = {
            'most_negative': f"{self.api_base_url}/most-negative",
            'turned_positive': f"{self.api_base_url}/turned-positive",
            'worsening': f"{self.api_base_url}/worsening-negative",
            'improving': f"{self.api_base_url}/improving-negative"
        }
        
        results = {}
        for key, url in endpoints.items():
            data = await self.fetch_json(url)
            if data and 'rates' in data:
                results[key] = data['rates']
            else:
                results[key] = []
                
        return results
    
    # ========== Price Methods ==========
    
    async def get_symbol_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get price data for a specific symbol
        
        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC', 'ETH')
            
        Returns:
            Price data dictionary or None if not found
        """
        # Normalize symbol
        symbol = symbol.upper().replace('USDT', '').strip()
        
        # First try our cache
        url = f"{self.api_base_url}/volatility-scanner/price-data"
        data = await self.fetch_json(url, timeout=5)
        
        if data and 'symbols' in data:
            # Search for the symbol in cached data
            for sym, info in data['symbols'].items():
                if sym.replace('-USDT', '').replace('USDT', '') == symbol:
                    return info
        
        # If not in cache, try Binance directly
        binance_url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}USDT"
        ticker_data = await self.fetch_json(binance_url, timeout=5)
        
        if ticker_data:
            # Transform to our standard format
            return {
                'price': float(ticker_data.get('lastPrice', 0)),
                'priceChangePercent': float(ticker_data.get('priceChangePercent', 0)),
                'volume': float(ticker_data.get('volume', 0))
            }
        
        return None
    
    # ========== Volatility Methods ==========
    
    async def get_volatility_scanner(self, timeframe: str = '1h', threshold: float = 5) -> Optional[Dict[str, Any]]:
        """
        Get volatility scanner data for coins exceeding threshold
        
        Args:
            timeframe: Time period (5m, 15m, 1h, 4h, 24h)
            threshold: Minimum percentage change threshold
            
        Returns:
            Volatility data dictionary
        """
        url = f"{self.api_base_url}/volatility-scanner?{timeframe}={threshold}"
        return await self.fetch_json(url)
    
    async def get_volatility_scanner_multi(self, timeframes_thresholds: Dict[str, float]) -> Dict[str, Any]:
        """
        Get volatility scanner data for multiple timeframes
        
        Args:
            timeframes_thresholds: Dict mapping timeframe to threshold (e.g., {'1h': 5, '24h': 25})
            
        Returns:
            Dict with results for each timeframe
        """
        results = {}
        for timeframe, threshold in timeframes_thresholds.items():
            data = await self.get_volatility_scanner(timeframe, threshold)
            if data and data.get('success'):
                # Find the matching threshold data
                for t in data.get('thresholds', []):
                    hours = t.get('hours', 0)
                    # Convert hours to timeframe string
                    if hours < 1:
                        tf = f"{int(hours * 60)}m"
                    else:
                        tf = f"{int(hours)}h"
                    
                    if tf == timeframe:
                        results[timeframe] = t
                        break
        return results
    
    async def get_symbol_volatility(self, symbol: str, timeframe: str = '1h') -> Optional[Dict[str, Any]]:
        """
        Get volatility data for a specific symbol
        
        Args:
            symbol: Cryptocurrency symbol
            timeframe: Time period for analysis
            
        Returns:
            Volatility metrics dictionary
        """
        symbol = symbol.upper().replace('USDT', '').strip()
        url = f"{self.api_base_url}/volatility-scanner/symbol/{symbol}?timeframe={timeframe}"
        return await self.fetch_json(url)
    
    # ========== Utility Methods ==========
    
    @staticmethod
    def format_symbol(symbol: str) -> str:
        """
        Format a symbol for display (remove -USDT suffix)
        
        Args:
            symbol: Raw symbol string
            
        Returns:
            Formatted symbol
        """
        return symbol.replace('-USDT', '').replace('USDT', '')
    
    @staticmethod
    def get_price_emoji(change: float, style: str = 'arrows') -> str:
        """
        Get emoji based on price change
        
        Args:
            change: Price change percentage
            style: 'arrows' for 📈📉, 'action' for 🚀💥
            
        Returns:
            Appropriate emoji
        """
        if style == 'action':
            return "🚀" if change > 0 else "💥"
        else:
            return "📈" if change > 0 else "📉"
    
    def format_volatility_coins(self, coins: List[Dict[str, Any]], limit: int = 3, 
                                style: str = 'action') -> List[str]:
        """
        Format a list of volatile coins for display
        
        Args:
            coins: List of coin data with percentChange and symbol
            limit: Maximum number of coins to format
            style: Emoji style ('action' or 'arrows')
            
        Returns:
            List of formatted strings
        """
        # Sort by absolute percentage change
        sorted_coins = sorted(coins, key=lambda x: abs(float(x['percentChange'])), reverse=True)[:limit]
        
        lines = []
        for coin in sorted_coins:
            percent = float(coin['percentChange'])
            emoji = self.get_price_emoji(percent, style)
            lines.append(f"{emoji} **{coin['symbol']}** `{percent:+.1f}%`")
        
        return lines
    
    def format_volatility_summary(self, timeframes_data: Dict[str, Any], 
                                  thresholds: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        """
        Process and format volatility data for multiple timeframes
        
        Args:
            timeframes_data: Raw data from get_volatility_scanner_multi
            thresholds: Threshold percentages for each timeframe
            
        Returns:
            Dict with formatted data for each timeframe
        """
        result = {}
        
        for timeframe, data in timeframes_data.items():
            if not data:
                result[timeframe] = {
                    'threshold': thresholds.get(timeframe, 5),
                    'formatted_lines': ["No movers"],
                    'total_count': 0
                }
                continue
            
            coins = data.get('coins', [])
            formatted_lines = self.format_volatility_coins(coins, limit=3)
            
            # Add count if more than 3
            if len(coins) > 3:
                formatted_lines.append(f"*...and {len(coins) - 3} more*")
            
            result[timeframe] = {
                'threshold': thresholds.get(timeframe, 5),
                'formatted_lines': formatted_lines if formatted_lines else ["No movers"],
                'total_count': len(coins)
            }
        
        return result
    
    def format_detailed_movers(self, coins: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, str]]:
        """
        Format coins for detailed mover display
        
        Args:
            coins: List of coin data
            limit: Maximum number to return
            
        Returns:
            List of dicts with formatted data for each coin
        """
        sorted_coins = sorted(coins, key=lambda x: abs(float(x['percentChange'])), reverse=True)[:limit]
        
        formatted = []
        for coin in sorted_coins:
            percent = float(coin['percentChange'])
            formatted.append({
                'symbol': coin['symbol'],
                'percent': percent,
                'percent_str': f"{percent:.2f}%",
                'price': float(coin['currentPrice']),
                'price_str': f"${float(coin['currentPrice']):.4f}",
                'chart_emoji': self.get_price_emoji(percent, 'arrows'),
                'action_emoji': self.get_price_emoji(percent, 'action')
            })
        
        return formatted
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 3) -> str:
        """
        Format a decimal as percentage string
        
        Args:
            value: Decimal value (e.g., 0.01 for 1%)
            decimals: Number of decimal places
            
        Returns:
            Formatted percentage string
        """
        return f"{value * 100:.{decimals}f}%"
    
    @staticmethod
    def get_rate_change(rate_data: Dict[str, Any], timeframe: str = '24h') -> float:
        """
        Extract rate change from rate data structure
        
        Args:
            rate_data: Rate data dictionary
            timeframe: Timeframe to get change for
            
        Returns:
            Change value as decimal
        """
        changes = rate_data.get('changes', {})
        # Try requested timeframe first, then fallback to any available
        timeframes = [timeframe, '24h', '12h', '8h', '4h']
        
        for tf in timeframes:
            if tf in changes:
                return float(changes[tf].get('change', 0))
        
        return 0.0
    
    @staticmethod
    def get_previous_rate(rate_data: Dict[str, Any]) -> float:
        """
        Extract previous rate from rate data
        
        Args:
            rate_data: Rate data dictionary
            
        Returns:
            Previous rate as decimal
        """
        prev_data = rate_data.get('changes', {}).get('prev', {})
        return float(prev_data.get('rate', 0))