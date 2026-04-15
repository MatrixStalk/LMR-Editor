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

        private static int Main()
        {
            var baseDir = AppDomain.CurrentDomain.BaseDirectory;
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
                if (!rpc.Initialize())
                {
                    Console.WriteLine("Discord RPC init failed. Is Discord running?");
                    return 2;
                }

                Console.WriteLine("Discord RPC started. Monitoring editor process...");
                var presenceSet = false;

                while (true)
                {
                    var editorRunning = IsEditorRunning(config.TargetProcessName);

                    if (editorRunning && !presenceSet)
                    {
                        rpc.SetPresence(BuildPresence(config, startedAt));
                        presenceSet = true;
                        Console.WriteLine("Presence enabled.");
                    }
                    else if (!editorRunning && presenceSet)
                    {
                        rpc.ClearPresence();
                        presenceSet = false;
                        Console.WriteLine("Presence cleared (editor closed).");

                        if (config.AutoExitWhenEditorClosed)
                        {
                            break;
                        }
                    }

                    rpc.Invoke();
                    Thread.Sleep(Math.Max(500, config.LoopDelayMs));
                }

                rpc.ClearPresence();
                rpc.Deinitialize();
            }

            Console.WriteLine("RPC launcher stopped.");
            return 0;
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
    }
}
