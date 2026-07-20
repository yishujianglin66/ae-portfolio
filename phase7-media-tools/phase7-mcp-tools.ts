/**
 * Phase7 - 素材获取与管理 MCP 工具
 *
 * 新增工具：
 * - download-media: 仅下载媒体文件（使用 yt-dlp，Node.js 纯 JS 实现，无需 Python）
 * - import-media-to-ae: 下载并导入媒体到 AE（一体化）
 * - import-footage-reliable: 可靠版素材导入（修复路径转义问题）
 *
 * 使用方式：在 MCP 服务器 index.ts 中调用 registerPhase7MediaTools(server, bridgeHelpers)
 */

import { z } from "zod";
import { PathUtils, MediaDownloader, AEImporter } from "./index.js";

export interface BridgeHelpers {
  clearResultsFile: () => void;
  writeCommandFile: (scriptName: string, parameters: Record<string, unknown>) => void;
  waitForBridgeResult: (scriptName: string, timeoutMs: number, intervalMs: number) => Promise<unknown>;
}

export function registerPhase7MediaTools(server: any, bridgeHelpers: BridgeHelpers): void {
  const { clearResultsFile, writeCommandFile, waitForBridgeResult } = bridgeHelpers;

  // ============================================================================
  // 工具 1: download-media
  // 下载媒体文件（不导入 AE）
  // ============================================================================
  server.tool(
    "download-media",
    "从 URL 下载视频或音频文件（使用 yt-dlp，支持 1000+ 网站）",
    {
      url: z.string().describe("媒体 URL（抖音、B站、YouTube 等）"),
      type: z.enum(["video", "audio"]).optional().default("video"),
      outputDir: z.string().optional().describe("自定义输出目录"),
      quality: z.enum(["best", "720p", "1080p"]).optional().default("best"),
    },
    async ({ url, type, outputDir, quality }) => {
      try {
        const ytDlpAvailable = await MediaDownloader.checkYtDlpAvailable();

        if (!ytDlpAvailable) {
          return {
            content: [
              {
                type: "text",
                text:
                  "⚠️ 警告：未找到 yt-dlp，请先安装 yt-dlp\n" +
                  "   下载地址: https://github.com/yt-dlp/yt-dlp/releases\n" +
                  "   安装后请确保在 PATH 中",
              },
            ],
            isError: true,
          };
        }

        const options = { outputDir, quality };
        let result;

        if (type === "audio") {
          result = await MediaDownloader.downloadAudio(url, options);
        } else {
          result = await MediaDownloader.downloadVideo(url, options);
        }

        return {
          content: [
            {
              type: "text",
              text: [
                "✅ 下载成功！",
                "",
                `📂 文件路径: ${result.filePath}`,
                `🔗 安全路径: ${result.safePath}`,
                "",
                "💡 提示: 使用 import-media-to-ae 可以同时下载并导入 AE",
              ].join("\n"),
            },
          ],
        };
      } catch (e) {
        return {
          content: [{ type: "text", text: `❌ 下载失败: ${String(e)}` }],
          isError: true,
        };
      }
    }
  );

  // ============================================================================
  // 工具 2: import-media-to-ae
  // 下载 + 导入 AE 一体化
  // ============================================================================
  server.tool(
    "import-media-to-ae",
    "从 URL 下载媒体并自动导入 After Effects（一体化工作流）",
    {
      url: z.string().describe("媒体 URL（抖音、B站、YouTube 等）"),
      type: z.enum(["video", "audio"]).optional().default("video"),
      compName: z.string().optional().describe("目标合成名称（不填则仅导入项目）"),
      outputDir: z.string().optional(),
      quality: z.enum(["best", "720p", "1080p"]).optional().default("best"),
    },
    async ({ url, type, compName, outputDir, quality }) => {
      try {
        // 1. 检查 yt-dlp
        const ytDlpAvailable = await MediaDownloader.checkYtDlpAvailable();

        if (!ytDlpAvailable) {
          return {
            content: [
              {
                type: "text",
                text:
                  "⚠️ 需要安装 yt-dlp\n" +
                  "下载地址: https://github.com/yt-dlp/yt-dlp/releases",
              },
            ],
            isError: true,
          };
        }

        // 2. 下载
        const options = { outputDir, quality };
        const downloadResult =
          type === "audio"
            ? await MediaDownloader.downloadAudio(url, options)
            : await MediaDownloader.downloadVideo(url, options);

        // 3. 准备 AE 导入脚本
        const importCmd = AEImporter.prepareImportCommand(
          downloadResult.filePath,
          compName
        );

        // 4. 调用 executeAtomScript（通过 AE Bridge）
        clearResultsFile();
        writeCommandFile("executeAtomScript", {
          scriptContent: importCmd.scriptContent,
        });
        const aeResult = await waitForBridgeResult("executeAtomScript", 15000, 250);

        return {
          content: [
            {
              type: "text",
              text: [
                "🎉 下载并导入成功！",
                "",
                "📥 下载信息:",
                `   - 文件: ${downloadResult.filePath}`,
                "",
                "🎬 AE 导入信息:",
                `   - 结果: ${JSON.stringify(aeResult, null, 2)}`,
              ].join("\n"),
            },
          ],
        };
      } catch (e) {
        return {
          content: [{ type: "text", text: `❌ 失败: ${String(e)}` }],
          isError: true,
        };
      }
    }
  );

  // ============================================================================
  // 工具 3: import-footage-reliable
  // 可靠版素材导入（解决路径转义问题，使用 executeAtomScript）
  // ============================================================================
  server.tool(
    "import-footage-reliable",
    "可靠版素材导入（修复路径转义问题，支持自动添加到合成）",
    {
      filePath: z.string().describe("素材文件的绝对路径"),
      compName: z.string().optional().describe("目标合成名称（可选）"),
      asSequence: z.boolean().optional().default(false),
      position: z.number().int().optional().describe("在合成中的插入位置"),
    },
    async ({ filePath, compName, asSequence, position }) => {
      try {
        // 使用可靠方法
        const importCmd = AEImporter.prepareImportCommand(filePath, compName);

        clearResultsFile();
        writeCommandFile("executeAtomScript", {
          scriptContent: importCmd.scriptContent,
        });

        const result = await waitForBridgeResult("executeAtomScript", 15000, 250);

        return {
          content: [
            {
              type: "text",
              text: `✅ 导入结果:\n${JSON.stringify(result, null, 2)}`,
            },
          ],
        };
      } catch (e) {
        return {
          content: [{ type: "text", text: `❌ 导入失败: ${String(e)}` }],
          isError: true,
        };
      }
    }
  );
}
