import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = 'https://8000-igyitwrl655jpdhlmwvph-a31b4228.sg1.manus.computer';

export default function ScraperPanel() {
  const [status, setStatus] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [apiToken, setApiToken] = useState('');
  const [showConfig, setShowConfig] = useState(false);

  // Get scraper status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/scraper/status`);
      const data = await response.json();
      setStatus(data);
      if (data.last_result) {
        setLastResult(data.last_result);
      }
    } catch (err) {
      console.error('Failed to fetch scraper status:', err);
    }
  }, []);

  // Periodically refresh status
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // Manually trigger scrape
  const handleScrape = async (source = null) => {
    setIsLoading(true);
    setError(null);
    try {
      let endpoint = `${API_BASE}/api/scraper/scrape`;
      if (source === 'reddit') {
        endpoint = `${API_BASE}/api/scraper/scrape/reddit`;
      } else if (source === 'twitter') {
        endpoint = `${API_BASE}/api/scraper/scrape/twitter`;
      }
      
      const response = await fetch(endpoint, {
        method: 'POST',
      });
      const data = await response.json();
      if (data.success) {
        setLastResult(data);
      } else {
        setError(data.error || 'Scrape failed');
      }
      await fetchStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Toggle mode
  const handleModeChange = async (newMode) => {
    try {
      await fetch(`${API_BASE}/api/scraper/mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode }),
      });
      await fetchStatus();
    } catch (err) {
      setError(err.message);
    }
  };

  // Switch data source
  const handleDataSourceChange = async (newSource) => {
    try {
      await fetch(`${API_BASE}/api/scraper/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data_source: newSource }),
      });
      await fetchStatus();
    } catch (err) {
      setError(err.message);
    }
  };

  // Update configuration
  const handleUpdateConfig = async () => {
    if (!apiToken) return;
    try {
      await fetch(`${API_BASE}/api/scraper/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_token: apiToken }),
      });
      setShowConfig(false);
      await fetchStatus();
    } catch (err) {
      setError(err.message);
    }
  };

  const isAutoMode = status?.mode === 'auto';
  const isReddit = status?.data_source === 'reddit';

  return (
    <div className="space-y-6">
      {/* Control Panel */}
      <div className="bg-gray-800 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Social Media Data Scraping</h3>
          <button
            onClick={() => setShowConfig(!showConfig)}
            className="text-gray-400 hover:text-white"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>

        {/* Configuration Panel */}
        {showConfig && (
          <div className="mb-4 p-4 bg-gray-700 rounded-lg">
            <label className="block text-sm text-gray-300 mb-2">Apify API Token</label>
            <div className="flex gap-2">
              <input
                type="password"
                value={apiToken}
                onChange={(e) => setApiToken(e.target.value)}
                placeholder="apify_api_xxx..."
                className="flex-1 bg-gray-600 text-white px-3 py-2 rounded text-sm"
              />
              <button
                onClick={handleUpdateConfig}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
              >
                Save
              </button>
            </div>
          </div>
        )}

        {/* Data Source Selection */}
        <div className="flex items-center gap-4 mb-4">
          <span className="text-gray-400 text-sm">Data source:</span>
          <div className="flex bg-gray-700 rounded-lg p-1">
            <button
              onClick={() => handleDataSourceChange('reddit')}
              className={`px-4 py-2 rounded text-sm transition-colors flex items-center gap-2 ${
                isReddit
                  ? 'bg-orange-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/>
              </svg>
              Reddit
            </button>
            <button
              onClick={() => handleDataSourceChange('twitter')}
              className={`px-4 py-2 rounded text-sm transition-colors flex items-center gap-2 ${
                !isReddit
                  ? 'bg-blue-500 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
              </svg>
              X (Twitter)
            </button>
          </div>
        </div>

        {/* Mode Switch */}
        <div className="flex items-center gap-4 mb-4">
          <span className="text-gray-400 text-sm">Scraper mode:</span>
          <div className="flex bg-gray-700 rounded-lg p-1">
            <button
              onClick={() => handleModeChange('manual')}
              className={`px-4 py-2 rounded text-sm transition-colors ${
                !isAutoMode
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Manual
            </button>
            <button
              onClick={() => handleModeChange('auto')}
              className={`px-4 py-2 rounded text-sm transition-colors ${
                isAutoMode
                  ? 'bg-green-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Auto (20 min)
            </button>
          </div>
        </div>

        {/* Scrape Button */}
        <button
          onClick={() => handleScrape()}
          disabled={isLoading}
          className={`w-full py-3 rounded-lg font-medium transition-colors ${
            isLoading
              ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
              : isReddit
                ? 'bg-orange-600 text-white hover:bg-orange-700'
                : 'bg-blue-600 text-white hover:bg-blue-700'
          }`}
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Scraping...
            </span>
          ) : (
            `Scrape ${isReddit ? 'Reddit' : 'X (Twitter)'} Now`
          )}
        </button>

        {/* Error Message */}
        {error && (
          <div className="mt-4 p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-300 text-sm">
            {error}
          </div>
        )}

        {/* StatusInfo */}
        {status && (
          <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-400">Last Scrape:</span>
              <span className="text-white ml-2">
                {status.last_scrape_time
                  ? new Date(status.last_scrape_time).toLocaleString('en-US')
                  : 'Never'}
              </span>
            </div>
            {isAutoMode && status.next_scrape_time && (
              <div>
                <span className="text-gray-400">Next Scrape:</span>
                <span className="text-green-400 ml-2">
                  {new Date(status.next_scrape_time).toLocaleString('en-US')}
                </span>
              </div>
            )}
            <div>
              <span className="text-gray-400">Search Terms:</span>
              <span className="text-white ml-2">
                {status.search_terms?.join(', ') || 'N/A'}
              </span>
            </div>
            {isReddit && (
              <div>
                <span className="text-gray-400">Subreddits:</span>
                <span className="text-orange-400 ml-2">
                  {status.subreddits?.map(s => `r/${s}`).join(', ') || 'N/A'}
                </span>
              </div>
            )}
            <div>
              <span className="text-gray-400">MaximumQuantity:</span>
              <span className="text-white ml-2">{status.max_items || 'N/A'}</span>
            </div>
          </div>
        )}
      </div>

      {/* Scrape result */}
      {lastResult && (
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">
            Scrape result
            <span className={`ml-2 text-sm ${lastResult.success ? 'text-green-400' : 'text-red-400'}`}>
              {lastResult.success ? 'Success' : 'Failed'}
            </span>
            {lastResult.source && (
              <span className={`ml-2 text-sm px-2 py-1 rounded ${
                lastResult.source === 'reddit' ? 'bg-orange-600' : 'bg-blue-500'
              }`}>
                {lastResult.source === 'reddit' ? 'Reddit' : 'Twitter'}
              </span>
            )}
          </h3>

          {lastResult.success && lastResult.posts?.length > 0 ? (
            <div className="space-y-4">
              <div className="text-sm text-gray-400">
                Scraped {lastResult.total_count} posts | 
                Time: {new Date(lastResult.scraped_at).toLocaleString('en-US')}
              </div>
              
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {lastResult.posts.map((post, index) => (
                  <div key={post.id || index} className="p-4 bg-gray-700 rounded-lg">
                    {/* Post Title (Reddit)*/}
                    {post.title && (
                      <h4 className="font-medium text-white mb-2">{post.title}</h4>
                    )}
                    
                    {/* Author Info */}
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-medium text-white">{post.author_name}</span>
                      <span className="text-gray-400 text-sm">
                        {post.source === 'reddit' ? `u/${post.author_username}` : `@${post.author_username}`}
                      </span>
                      {post.subreddit && (
                        <span className="text-orange-400 text-sm">r/{post.subreddit}</span>
                      )}
                    </div>
                    
                    {/* Post Content */}
                    <p className="text-gray-300 text-sm mb-2">
                      {post.text?.substring(0, 300)}
                      {post.text?.length > 300 && '...'}
                    </p>
                    
                    {/* Statistics */}
                    <div className="flex gap-4 text-xs text-gray-500">
                      <span>{post.source === 'reddit' ? '⬆️' : '❤️'} {post.score || 0}</span>
                      <span>💬 {post.comments || 0}</span>
                      {post.url && (
                        <a 
                          href={post.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-blue-400 hover:underline"
                        >
                          View Original
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : lastResult.success ? (
            <div className="text-gray-400 text-center py-8">
              No posts scraped
            </div>
          ) : (
            <div className="text-red-400 text-center py-8">
              {lastResult.error || 'ScrapeFailed'}
            </div>
          )}
        </div>
      )}

      {/* Usage Instructions */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Usage Instructions</h3>
        <div className="text-sm text-gray-400 space-y-2">
          <p>• <strong className="text-white">Data Source Selection</strong>: Supports Reddit and X (Twitter) platforms</p>
          <p>• <strong className="text-orange-400">Reddit</strong>: Scrapes crypto subreddits like r/Bitcoin, r/CryptoCurrency</p>
          <p>• <strong className="text-blue-400">X (Twitter)</strong>: Searches tweets for keywords like Bitcoin, Ethereum</p>
          <p>• <strong className="text-white">Manual mode</strong>: Click the "Scrape Now" button to manually trigger a data scrape</p>
          <p>• <strong className="text-white">Auto mode</strong>: System automatically scrapes every 20 minutes</p>
          <p>• Scraped data is used for sentiment analysis to support trading decisions</p>
          <p className="text-yellow-400">⚠️ Note: Each scrape consumes Apify credits, please use wisely</p>
        </div>
      </div>
    </div>
  );
}
