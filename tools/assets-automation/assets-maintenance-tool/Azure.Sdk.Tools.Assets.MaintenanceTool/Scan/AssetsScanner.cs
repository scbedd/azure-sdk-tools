using System;
using System.Text.Json;
using Azure.Sdk.Tools.Assets.MaintenanceTool.Model;
using Azure.Sdk.Tools.TestProxy.Common.Exceptions;
using Azure.Sdk.Tools.TestProxy.Store;
using Microsoft.Extensions.FileSystemGlobbing;

namespace Azure.Sdk.Tools.Assets.MaintenanceTool.Scan
{
    /// <summary>
    /// Used to walk through repo configurations and locate all assets.
    /// </summary>
    public class AssetsScanner
    {
        public AssetsScanner() {}
        GitProcessHandler handler = new GitProcessHandler();

        public AssetsResultSet Scan(RunConfiguration config, AssetsResultSet? previousOutput)
        {
            var resultSet = new AssetsResultSet(new List<AssetsResult>());

            Parallel.ForEach(config.Repos, repoConfig =>
            {
                var results = ScanRepo(repoConfig, previousOutput);
                resultSet.Results.AddRange(results);
            });

            return resultSet;
        }

        public List<AssetsResult> ScanRepo(RepoConfiguration config, AssetsResultSet? previousOutput)
        {
            var targetRepoUri = $"https://github.com/{config.Repo}.git";
            var workingDirectory = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
            var results = new List<AssetsResult>();

            try
            {
                if(!Directory.Exists(workingDirectory))
                {
                    Directory.CreateDirectory(workingDirectory);
                }

                foreach(var branch in config.Branches)
                {
                    var commits = CloneBranch(targetRepoUri, branch, config.ScanStartDate, workingDirectory);
                    results.AddRange(FindAssetsResults(config.Repo, commits, workingDirectory));
                }
            }
            finally
            {
                CleanupWorkingDirectory(workingDirectory);
            }

            return results;
        }

        private void SetPermissionsAndDelete(string gitfolder)
        {
            File.SetAttributes(gitfolder, FileAttributes.Normal);

            string[] files = Directory.GetFiles(gitfolder);
            string[] dirs = Directory.GetDirectories(gitfolder);

            foreach (string file in files)
            {
                File.SetAttributes(file, FileAttributes.Normal);
                File.Delete(file);
            }

            foreach (string dir in dirs)
            {
                SetPermissionsAndDelete(dir);
            }

            Directory.Delete(gitfolder, false);
        }


        private void CleanupWorkingDirectory(string workingDirectory)
        {
            var possibleGitDir = Path.Combine(workingDirectory, ".git");

            if (Directory.Exists(possibleGitDir))
            {
                SetPermissionsAndDelete(possibleGitDir);
            }

            Directory.Delete(workingDirectory, true);
        }

        /// <summary>
        /// Clones a specific branch, then returns all commit shas newer than our targeted date.
        /// </summary>
        /// <param name="uri"></param>
        /// <param name="branch"></param>
        /// <param name="workingDirectory"></param>
        /// <returns></returns>
        public List<string> CloneBranch(string uri, string branch, DateTime since, string workingDirectory)
        {
            var commitSHAs = new List<string>();
            try
            {
                // if git is already initialized, we just need to checkout a specific branch
                if (!Directory.Exists(Path.Combine(workingDirectory, ".git"))) {
                    handler.Run($"clone {uri} --branch {branch} --single-branch .", workingDirectory);
                }
                else
                {
                    handler.Run($"checkout -b {branch}", workingDirectory);
                    handler.Run($"pull origin {branch}", workingDirectory);
                    Cleanup(workingDirectory);
                }

                var tagResult = handler.Run($"log --since={since.ToString("yyyy-MM-dd")} --simplify-by-decoration --format=format:%H", workingDirectory);
                commitSHAs.AddRange(tagResult.StdOut.Split(Environment.NewLine).Select(x => x.Trim()).Where(x => !string.IsNullOrWhiteSpace(x)));
            }
            catch(GitProcessException gitException)
            {
                // special case handling here?
                Console.WriteLine(gitException.ToString());
                Environment.Exit(1);
            }
            catch(Exception e)
            {
                Console.WriteLine(e.ToString());
                Environment.Exit(1);
            }

            return commitSHAs;
        }

        public void Cleanup(string workingDirectory)
        {
            try
            {
                handler.Run("clean -xdf", workingDirectory);
            }
            catch (GitProcessException gitException)
            {
                // special case handling here?
                Console.WriteLine(gitException.ToString());
                Environment.Exit(1);
            }
            catch (Exception e)
            {
                Console.WriteLine(e.ToString());
                Environment.Exit(1);
            }
        }

        private class Assets
        {
            public Assets()
            {
                AssetsRepo = string.Empty;
                Tag = string.Empty;
            }

            public string AssetsRepo { get; set; }

            public string Tag { get; set; }
        }

        private Assets? ExtractAssetsData(string assetsJson)
        {
            return JsonSerializer.Deserialize<Assets>(File.ReadAllText(assetsJson));
        }

        public List<AssetsResult> ScanDirectory(string repo, string commit, string workingDirectory)
        {
            Matcher matcher = new();
            List<AssetsResult> locatedAssets = new List<AssetsResult>();
            matcher.AddIncludePatterns(new[] { "**/assets.json" });
            IEnumerable<string> assetsJsons = matcher.GetResultsInFullPath(workingDirectory);

            foreach(var assetsJson in assetsJsons)
            {
                var path = Path.GetRelativePath(workingDirectory, assetsJson).Replace("\\", "/");
                var assetsData = ExtractAssetsData(assetsJson);

                if (assetsData != null)
                {
                    var newResult = new AssetsResult(repo, commit, path, assetsData.Tag, assetsData.AssetsRepo, null);
                    locatedAssets.Add(newResult);
                }
            }

            return locatedAssets;
        }

        public List<AssetsResult> FindAssetsResults(string repo, List<string> commits, string workingDirectory)
        {
            var allResults = new List<AssetsResult>();
            foreach(var commit in commits)
            {
                handler.Run($"checkout {commit}", workingDirectory);
                Cleanup(workingDirectory);
                allResults.AddRange(ScanDirectory(repo, commit, workingDirectory));
            }

            return allResults;
        }
    }
}
