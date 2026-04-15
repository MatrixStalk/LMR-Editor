using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using DiscordRPC;
using Newtonsoft.Json;

namespace LmrDiscordRpcLauncher
{
    internal sealed class RpcConfig
    {
        public RpcConfig()
        {
            DiscordApplicationId = "PUT_YOUR_DISCORD_APP_ID_HERE";
            TargetProcessName = "LMR Scenario Editor";
            TargetExePath = ".\\LMR Scenario Editor.exe";
            AutoLaunchEditor = false;
            AutoExitWhenEditorClosed = true;
            LoopDelayMs = 2000;
            Details = "Editing scenarios";
            State = "LMR Scenario Editor";
            LargeImageKey = "app";
            LargeImageText = "LMR Scenario Editor";
            SmallImageKey = "";
            SmallImageText = "";
            PartyId = "";
            PartySize = 0;
            PartyMax = 0;
        }

        public string DiscordApplicationId { get; set; }
        public string TargetProcessName { get; set; }
        public string TargetExePath { get; set; }
        public bool AutoLaunchEditor { get; set; }
        public bool AutoExitWhenEditorClosed { get; set; }
        public int LoopDelayMs { get; set; }
        public string Details { get; set; }
        public string State { get; set; }
        public string LargeImageKey { get; set; }
        public string LargeImageText { get; set; }
        public string SmallImageKey { get; set; }
        public string SmallImageText { get; set; }
        public string PartyId { get; set; }
        public int PartySize { get; set; }
        public int PartyMax { get; set; }
    }

    internal static class Program
    {
        private const string ConfigFileName = "discord-rpc-config.json";
        private const string LogFileName = "rpc.log";
        private static string _logPath;

        private static int Main()
        {
            try
            {
            var baseDir = AppDomain.CurrentDomain.BaseDirectory;
            _logPath = Path.Combine(baseDir, LogFileName);
            var configPath = Path.Combine(baseDir, ConfigFileName);
            var config = LoadOrCreateConfig(configPath);

            if (string.IsNullOrWhiteSpace(config.DiscordApplicationId) || config.DiscordApplicationId.Contains("PUT_YOUR"))
            {
                Console.WriteLine("Set DiscordApplicationId in discord-rpc-config.json first.");
                return 1;
            }

            if (config.AutoLaunchEditor)
            {
                TryLaunchEditor(baseDir, config.TargetExePath);
            }

            var startedAt = DateTime.UtcNow;
            using (var rpc = new DiscordRpcClient(config.DiscordApplicationId))
            {
                rpc.Logger = null;
                WaitForInitializeRpc(rpc, config);

                Console.WriteLine("Discord RPC started. Monitoring editor process...");
                Log("Discord RPC started. Monitoring editor process...");
                var presenceSet = false;

                while (true)
                {
                    var editorRunning = IsEditorRunning(config.TargetProcessName);

                    if (editorRunning && !presenceSet)
                    {
                        try
                        {
                            rpc.SetPresence(BuildPresence(config, startedAt));
                            presenceSet = true;
                            Console.WriteLine("Presence enabled.");
                            Log("Presence enabled.");
                        }
                        catch (Exception ex)
                        {
                            Console.WriteLine("SetPresence failed: " + ex.Message);
                            Log("SetPresence failed: " + ex);
                            WaitForInitializeRpc(rpc, config);
                        }
                    }
                    else if (!editorRunning && presenceSet)
                    {
                        rpc.ClearPresence();
                        presenceSet = false;
                        Console.WriteLine("Presence cleared (editor closed).");
                        Log("Presence cleared (editor closed).");

                        if (config.AutoExitWhenEditorClosed)
                        {
                            break;
                        }
                    }

                    try
                    {
                        rpc.Invoke();
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine("RPC invoke error: " + ex.Message);
                        Log("RPC invoke error: " + ex);
                        WaitForInitializeRpc(rpc, config);
                    }
                    Thread.Sleep(Math.Max(500, config.LoopDelayMs));
                }

                rpc.ClearPresence();
                rpc.Deinitialize();
            }

            Console.WriteLine("RPC launcher stopped.");
            Log("RPC launcher stopped.");
            return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine("Fatal RPC launcher error: " + ex.Message);
                Log("Fatal RPC launcher error: " + ex);
                return 10;
            }
        }

        private static void WaitForInitializeRpc(DiscordRpcClient rpc, RpcConfig config)
        {
            var attempt = 0;
            while (true)
            {
                attempt++;
                try
                {
                    if (rpc.Initialize())
                    {
                        if (attempt > 1)
                        {
                            Log("Discord RPC connected on attempt " + attempt + ".");
                        }
                        return;
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine("Discord RPC init attempt " + attempt + " failed: " + ex.Message);
                    Log("Discord RPC init attempt " + attempt + " failed: " + ex);
                }

                if (config.AutoExitWhenEditorClosed && !IsEditorRunning(config.TargetProcessName))
                {
                    Log("Stopping init retries: editor is not running.");
                    return;
                }

                Console.WriteLine("Waiting for Discord... (attempt " + attempt + ")");
                Thread.Sleep(2000);
            }
        }

        private static RichPresence BuildPresence(RpcConfig config, DateTime startedAt)
        {
            var presence = new RichPresence
            {
                Details = config.Details,
                State = config.State,
                Timestamps = new Timestamps(startedAt),
                Assets = new Assets
                {
                    LargeImageKey = config.LargeImageKey,
                    LargeImageText = config.LargeImageText,
                    SmallImageKey = string.IsNullOrWhiteSpace(config.SmallImageKey) ? null : config.SmallImageKey,
                    SmallImageText = string.IsNullOrWhiteSpace(config.SmallImageText) ? null : config.SmallImageText
                }
            };

            if (!string.IsNullOrWhiteSpace(config.PartyId) && config.PartyMax > 0)
            {
                presence.Party = new Party
                {
                    ID = config.PartyId,
                    Size = Math.Max(0, config.PartySize),
                    Max = config.PartyMax
                };
            }

            return presence;
        }

        private static bool IsEditorRunning(string processName)
        {
            if (string.IsNullOrWhiteSpace(processName))
            {
                return false;
            }

            return Process.GetProcesses().Any(p =>
            {
                try
                {
                    return string.Equals(p.ProcessName, processName, StringComparison.OrdinalIgnoreCase);
                }
                catch
                {
                    return false;
                }
            });
        }

        private static void TryLaunchEditor(string baseDir, string relativeOrAbsoluteExePath)
        {
            try
            {
                var path = relativeOrAbsoluteExePath;
                if (!Path.IsPathRooted(path))
                {
                    path = Path.GetFullPath(Path.Combine(baseDir, path));
                }

                if (File.Exists(path))
                {
                    Process.Start(path);
                    Console.WriteLine("Editor launched: " + path);
                }
                else
                {
                    Console.WriteLine("Editor exe not found: " + path);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("Failed to launch editor: " + ex.Message);
            }
        }

        private static RpcConfig LoadOrCreateConfig(string configPath)
        {
            if (!File.Exists(configPath))
            {
                var defaultConfig = new RpcConfig();
                var text = JsonConvert.SerializeObject(defaultConfig, Formatting.Indented);
                File.WriteAllText(configPath, text);
                return defaultConfig;
            }

            try
            {
                var text = File.ReadAllText(configPath);
                var cfg = JsonConvert.DeserializeObject<RpcConfig>(text);
                return cfg ?? new RpcConfig();
            }
            catch
            {
                return new RpcConfig();
            }
        }

        private static void Log(string message)
        {
            try
            {
                var line = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " | " + message;
                Console.WriteLine(line);
                if (!string.IsNullOrWhiteSpace(_logPath))
                {
                    File.AppendAllText(_logPath, line + Environment.NewLine);
                }
            }
            catch
            {
            }
        }
    }
}
