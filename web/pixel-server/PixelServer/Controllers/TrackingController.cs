using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.ApplicationInsights;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Primitives;

namespace PixelServer.Controllers
{
    [Route("api/impressions")]
    [ApiController]
    public class TrackingController : ControllerBase
    {
        // populated and returned as 1 pixel image
        private static readonly string imgPath = AppDomain.CurrentDomain.BaseDirectory + "/Etc/pixel.png";
        private static readonly byte[] img = System.IO.File.ReadAllBytes(imgPath);

        private readonly IMemoryCache _cache;
        private readonly TelemetryClient telemetry;

        public TrackingController(IMemoryCache memoryCache, TelemetryClient telemetry)
        {
            _cache = memoryCache;
            this.telemetry = telemetry;
        }

        /// <summary>
        /// Currently the only entrypoint, services a 1 pixel image while recording that there was an impression for the specific path.
        /// 
        /// Uses in-memory cache of afore-seen IPs to recognize a "duplicate" impression. The addresses themselves are not recorded.
        /// </summary>
        /// <param name="path"></param>
        /// <returns></returns>
        [HttpGet]
        public async Task<ActionResult> Get(string path)
        {
            await trackEventAsync(path);

            return File(img, "image/png");
        }

        private async Task trackEventAsync(string path)
        {
            await Task.Run(() =>
            {
                telemetry.TrackEvent("PixelImpression", new Dictionary<string, string>()
                {
                    { "visitor_duplicate", getCachedVisitorStatus(getRequestAddress()) },
                    { "visitor_path", path }
                });
            });
        }

        private string getCachedVisitorStatus(System.Net.IPAddress address)
        {
            if (!_cache.TryGetValue(address, out _))
            {
                // Set cache options.
                var cacheEntryOptions = new MemoryCacheEntryOptions()
                    // Keep in cache for this time, reset time if accessed.
                    .SetSlidingExpiration(TimeSpan.FromHours(1));

                // Save data in cache.
                _cache.Set(address, DateTime.UtcNow, cacheEntryOptions);

                return "false";
            }

            return "true";
        }

        private System.Net.IPAddress getRequestAddress()
        {
            return Request.HttpContext.Connection.RemoteIpAddress;
        }
    }
}
