import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

interface MarkdownProps {
  children: string;
  className?: string;
}

export function Markdown({ children, className }: MarkdownProps) {
  // Detect if we're rendering small text
  const isSmallText = className?.includes("text-xs");

  return (
    <div className={cn("prose prose-sm max-w-none [&>*:last-child]:mb-0", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
      components={{
        // Headings - subtle, refined
        h1: ({ children, ...props }) => (
          <h1 className="text-lg font-semibold text-gray-900 mt-6 mb-3" {...props}>
            {children}
          </h1>
        ),
        h2: ({ children, ...props }) => (
          <h2 className="text-base font-semibold text-gray-900 mt-5 mb-2" {...props}>
            {children}
          </h2>
        ),
        h3: ({ children, ...props }) => (
          <h3 className="text-sm font-semibold text-gray-900 mt-4 mb-2" {...props}>
            {children}
          </h3>
        ),

        // Paragraphs - clean spacing
        p: ({ children, ...props }) => (
          <p className={cn(
            "leading-relaxed mb-3",
            isSmallText ? "text-xs" : "text-sm",
            "text-inherit"
          )} {...props}>
            {children}
          </p>
        ),

        // Lists - minimal bullets, good spacing
        ul: ({ children, ...props }) => (
          <ul className="space-y-1 mb-3 ml-4 list-none" {...props}>
            {children}
          </ul>
        ),
        ol: ({ children, ...props }) => (
          <ol className="space-y-1 mb-3 ml-4 list-decimal list-inside" {...props}>
            {children}
          </ol>
        ),
        li: ({ children, ...props }) => {
          // Check if parent is ordered list
          const isOrdered = props.ordered;

          if (isOrdered) {
            return (
              <li className={cn(
                "leading-relaxed",
                isSmallText ? "text-xs" : "text-sm",
                "text-inherit"
              )} {...props}>
                {children}
              </li>
            );
          }

          return (
            <li className={cn(
              "leading-relaxed flex",
              isSmallText ? "text-xs" : "text-sm",
              "text-inherit"
            )} {...props}>
              <span className="inline-block mr-2 text-gray-400 select-none">•</span>
              <span className="flex-1">{children}</span>
            </li>
          );
        },

        // Code - subtle background
        code: ({ children, ...props }) => {
          // Check if it's inline code (no className) or code block
          const isInline = !props.className;

          if (isInline) {
            return (
              <code
                className="px-1.5 py-0.5 bg-gray-100 text-gray-800 rounded text-xs font-mono"
                {...props}
              >
                {children}
              </code>
            );
          }

          // Code block
          return (
            <code
              className="block bg-gray-50 text-gray-800 rounded-lg p-3 text-xs font-mono overflow-x-auto mb-3"
              {...props}
            >
              {children}
            </code>
          );
        },

        // Links - subtle underline
        a: ({ children, href, ...props }) => (
          <a
            href={href}
            className="text-gray-700 underline decoration-gray-300 hover:decoration-gray-500 transition-colors"
            target="_blank"
            rel="noopener noreferrer"
            {...props}
          >
            {children}
          </a>
        ),

        // Blockquotes - subtle left border
        blockquote: ({ children, ...props }) => (
          <blockquote
            className="border-l-2 border-gray-200 pl-4 my-3 text-sm text-gray-600 italic"
            {...props}
          >
            {children}
          </blockquote>
        ),

        // Tables - clean, minimal
        table: ({ children, ...props }) => (
          <div className="overflow-x-auto mb-3">
            <table className="min-w-full divide-y divide-gray-200" {...props}>
              {children}
            </table>
          </div>
        ),
        thead: ({ children, ...props }) => (
          <thead className="bg-gray-50" {...props}>
            {children}
          </thead>
        ),
        tbody: ({ children, ...props }) => (
          <tbody className="bg-white divide-y divide-gray-100" {...props}>
            {children}
          </tbody>
        ),
        th: ({ children, ...props }) => (
          <th
            className="px-3 py-2 text-left text-xs font-medium text-gray-600 uppercase tracking-wider"
            {...props}
          >
            {children}
          </th>
        ),
        td: ({ children, ...props }) => (
          <td className="px-3 py-2 text-sm text-gray-700" {...props}>
            {children}
          </td>
        ),

        // Horizontal rules - subtle
        hr: ({ ...props }) => (
          <hr className="my-4 border-gray-200" {...props} />
        ),

        // Strong/Bold - medium weight for subtlety
        strong: ({ children, ...props }) => (
          <strong className="font-medium text-gray-900" {...props}>
            {children}
          </strong>
        ),

        // Emphasis/Italic
        em: ({ children, ...props }) => (
          <em className="italic text-gray-700" {...props}>
            {children}
          </em>
        ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
