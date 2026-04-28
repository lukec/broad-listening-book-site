#!/usr/bin/env python3
"""
Build a multilingual static web-book edition from the manuscript markdown.

Default output:
    site/
      index.html
      assets/
      en/
      ja/
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

import markdown

from .config import default_book_source_dir, default_site_output_dir, SITE_REPO_ROOT

SHAPE_UP_TYPEKIT_CSS = "https://use.typekit.net/xig7qap.css"
DESIGN_CREDIT_COMMENT = (
    "<!-- Design inspiration: Basecamp's Shape Up web book "
    "(https://basecamp.com/shapeup). -->"
)
LANDING_IMAGE = "images/01_broadlistening.png"
DD2030_URL = "https://dd2030.org/"
SOURCE_REPO_URL = "https://github.com/digitaldemocracy2030/broad-listening-book"
SITE_REPO_URL = "https://github.com/lukec/broad-listening-book-site"
SITE_ISSUES_URL = f"{SITE_REPO_URL}/issues"
SITE_NEW_ISSUE_URL = f"{SITE_REPO_URL}/issues/new?template=book-site-problem.yml"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
TRANSLATION_NOTE_TEXT = (
    "Translation note (English edition): Original Japanese authorship is preserved "
    "throughout this book. Any errors in the English translation are the translator’s own."
)


@dataclass(frozen=True)
class LanguageConfig:
    code: str
    lang_attr: str
    title: str
    subtitle: str
    author: str
    source_root: Path
    order_file: Path
    label: str
    edition_label: str
    body_class: str
    part_labels: list[tuple[tuple[int, int], str]]


@dataclass
class Chapter:
    source_rel: str
    output_rel: str
    canonical_rel: str
    part_label: str
    chapter_label: str
    title: str
    headings: list[tuple[str, str]]
    body_html: str


LANGUAGE_UI = {
    "en": {
        "all_languages": "← All languages",
        "back_to_edition": "← English edition",
        "sections_on_page": "Sections on this page",
        "chapters_in_language": "Chapters in this language",
        "draft_badge": "Pre-release Draft",
        "start_reading": "Start reading →",
        "continue_reading": "Continue reading →",
        "continue_reading_short": "Continue reading",
        "previous_chapter": "← Previous chapter",
        "next_chapter": "Next chapter →",
        "next_prefix": "Next:",
        "back_to_contents": "Back to contents →",
        "language_switch": "Languages",
        "chapter": "Chapter",
        "column": "Column",
        "preface": "Preface",
        "endorsement": "Endorsement",
        "appendix": "Appendix",
        "choose_language": "Choose a language",
        "choose_language_subtitle": "One web edition for every language of the book.",
        "open_edition": "Open edition",
        "site_suffix": "English Web Edition",
        "about_this_book": "About this Book",
        "report_problem": "Problems with the book?",
        "share_passage": "Share passage",
        "copied_passage": "Copied",
    },
    "ja": {
        "all_languages": "← 言語一覧へ",
        "back_to_edition": "← 日本語版へ",
        "sections_on_page": "このページの節",
        "chapters_in_language": "この言語の章一覧",
        "draft_badge": "先行公開ドラフト",
        "start_reading": "読み始める →",
        "continue_reading": "続きを読む →",
        "continue_reading_short": "続きを読む",
        "previous_chapter": "← 前の章",
        "next_chapter": "次の章 →",
        "next_prefix": "次:",
        "back_to_contents": "目次へ戻る →",
        "language_switch": "言語",
        "chapter": "第",
        "column": "コラム",
        "preface": "序文",
        "endorsement": "推薦文",
        "appendix": "付録",
        "choose_language": "言語を選択",
        "choose_language_subtitle": "この書籍を同じサイトで多言語公開します。",
        "open_edition": "版を開く",
        "site_suffix": "日本語版Webブック",
        "about_this_book": "この本について",
        "report_problem": "本の問題を報告する",
        "share_passage": "選択箇所を共有",
        "copied_passage": "コピーしました",
    },
}

STYLE_CSS = """
:root {
  --color-text: 0, 0, 0;
  --color-background: 255, 255, 255;
  --color-link: 0, 0, 0;
  --type-base: calc(1.6em + 0.5vw);
  --type-xxxx-small: 30%;
  --type-xxx-small: 55%;
  --type-xx-small: 65%;
  --type-x-small: 75%;
  --type-small: 85%;
  --type-medium: 100%;
  --type-large: 120%;
  --type-x-large: 160%;
  --type-xx-large: 200%;
  --type-xxx-large: 300%;
  --type-xxxx-large: 400%;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

::selection {
  color: rgb(var(--color-background));
  background-color: rgb(var(--color-text));
}

html {
  font-size: 16px;
  scroll-behavior: smooth;
}

@supports(display: grid) {
  html {
    font-size: 10px;
  }
}

body {
  margin: 0;
  padding: 0;
  font-family: ff-meta-serif-web-pro, serif;
  font-size: var(--type-base);
  color: rgb(var(--color-text));
  background-color: rgb(var(--color-background));
  overflow-x: hidden;
}

.draft-ribbon {
  position: fixed;
  top: 1.4rem;
  left: 1.4rem;
  z-index: 30;
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.78rem 1.3rem;
  border: 0.22rem solid #3b2b34;
  border-radius: 1.9rem;
  background:
    radial-gradient(circle at 18% 28%, rgba(255, 255, 255, 0.95) 0 0.45rem, transparent 0.5rem),
    radial-gradient(circle at 82% 72%, rgba(255, 255, 255, 0.8) 0 0.3rem, transparent 0.35rem),
    linear-gradient(135deg, #ffd6ea 0%, #ffe7f4 48%, #fff0bf 100%);
  color: #2f2229;
  font-family: ff-meta-web-pro, ff-meta-serif-web-pro, serif;
  font-size: 1.3rem;
  font-weight: bold;
  letter-spacing: 0.04em;
  box-shadow:
    0.2rem 0.2rem 0 #fff8fb,
    0.55rem 0.55rem 0 #ff9fc4;
  transform: rotate(-5deg);
}

.draft-ribbon::before,
.draft-ribbon::after {
  content: "o";
  position: absolute;
  color: #ff7eb0;
  font-family: Georgia, serif;
  font-size: 1.3rem;
  line-height: 1;
  opacity: 0.8;
}

.draft-ribbon::before {
  top: -0.45rem;
  left: 0.95rem;
}

.draft-ribbon::after {
  right: 1.05rem;
  bottom: -0.5rem;
}

.draft-ribbon__icon {
  display: inline-flex;
  width: 1.45rem;
  height: 1.45rem;
  flex: 0 0 auto;
}

.draft-ribbon__icon svg {
  width: 100%;
  height: 100%;
}

.draft-ribbon__icon path {
  fill: #2f2229;
}

.draft-ribbon__icon--heart {
  width: 1.25rem;
  height: 1.25rem;
  transform: rotate(-8deg);
}

.draft-ribbon__text {
  position: relative;
  top: 0.02rem;
}

body.lang-ja {
  font-family:
    ff-meta-serif-web-pro,
    "Hiragino Mincho ProN",
    "Yu Mincho",
    "Noto Serif JP",
    serif;
}

a {
  color: rgb(var(--color-link));
}

a:hover,
a:visited {
  color: rgb(var(--color-link));
}

h1,
h2,
h3,
h4,
h5,
h6 {
  margin: 1.5em 0 0 0;
  padding: 0;
  font-size: var(--type-large);
  font-weight: bold;
  line-height: 1.2;
}

h1 {
  font-size: var(--type-xx-large);
}

h2 {
  font-size: var(--type-x-large);
}

h3 {
  margin-bottom: -0.25em;
}

h4 {
  font-size: var(--type-small);
  margin-top: 1.25em;
}

p {
  margin: 1em 0 0 0;
  font-size: var(--type-medium);
  line-height: 1.5;
}

ul,
ol {
  margin: 1em 0 0 1em;
  padding: 0;
  line-height: 1.5;
}

hr {
  height: 0;
  margin: 3em 0;
  border: 0;
  border-top: 0.1rem solid rgb(var(--color-text));
}

blockquote {
  margin: 1em 0 0 0;
  padding: 0 0 0 1em;
  border-left: 0.2rem solid rgb(var(--color-text));
  font-style: italic;
}

code {
  position: relative;
  padding: 0.25rem 0.5rem;
  border-radius: 0.2rem;
  background-color: rgba(var(--color-link), 0.075);
  font-size: var(--type-x-small);
  font-family: SFMono-Regular, Consolas, Liberation Mono, Menlo, Courier, monospace;
}

.wordmark-inline {
  font-family: SFMono-Regular, Consolas, Liberation Mono, Menlo, Courier, monospace;
  font-size: 0.92em;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

pre {
  overflow-x: auto;
}

pre code {
  display: block;
  padding: 1.25rem;
}

pre code.language-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

img {
  max-width: 100%;
  border-radius: 1rem;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.25em 0 0 0;
  font-size: var(--type-small);
}

th,
td {
  padding: 0.7em 0.9em;
  border: 0.1rem solid rgba(0, 0, 0, 0.16);
  text-align: left;
  vertical-align: top;
}

.sr-only {
  border: 0;
  clip: rect(0 0 0 0);
  height: 1px;
  margin: -1px;
  overflow: hidden;
  padding: 0;
  position: absolute;
  width: 1px;
}

.button {
  display: inline-flex;
  align-items: center;
  padding: 0.5em 0.75em;
  border: 0.2rem solid rgb(var(--color-link));
  background-color: rgb(var(--color-link));
  color: rgb(var(--color-background));
  border-radius: 1.25em;
  font-size: inherit;
  font-family: inherit;
  font-weight: bold;
  line-height: 1.25;
  text-decoration: none;
}

.button:hover,
.button:visited {
  color: rgb(var(--color-background));
}

.button--ghost {
  background-color: transparent;
  color: rgb(var(--color-text));
}

.button--ghost:hover,
.button--ghost:visited {
  color: rgb(var(--color-text));
}

.continue-reading {
  display: none;
  width: 100%;
  max-width: 46rem;
  align-items: center;
  gap: 0.9rem;
  padding: 0.95rem 1.2rem;
  border: 0.1rem solid rgba(0, 0, 0, 0.12);
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.03);
  text-decoration: none;
  color: rgb(var(--color-text));
}

.continue-reading.is-visible {
  display: inline-flex;
}

.continue-reading__eyebrow {
  display: block;
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.2rem;
  font-size: var(--type-xxxx-small);
}

.continue-reading__title {
  display: block;
  margin: 0.1rem 0 0;
  font-size: var(--type-x-small);
  line-height: 1.2;
}

.continue-reading__arrow {
  margin-left: auto;
  font-size: var(--type-small);
  white-space: nowrap;
}

.root {
  width: min(88rem, calc(100vw - 3rem));
  margin: 0 auto;
  padding: 1.5em 0 4em;
}

.root__main {
  max-width: 64rem;
}

.root__title {
  margin: 0;
  font-size: var(--type-xxx-large);
  line-height: 1.05;
}

.root__subtitle {
  margin: 0;
  font-size: var(--type-xx-large);
  line-height: 1.15;
}

.root__languages {
  display: flex;
  flex-wrap: wrap;
  gap: 1em;
  margin-top: 1.75em;
}

.root__language {
  margin: 0;
}

.root__notes {
  margin-top: 4em;
  padding-top: 1.25em;
  border-top: 0.1rem solid rgb(var(--color-text));
  max-width: 56rem;
}

.root__notes-title {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.3rem;
  font-size: var(--type-xx-small);
}

.root__notes p {
  font-size: var(--type-small);
}

.site-footer {
  max-width: 46em;
  margin-top: 3em;
  padding-top: 1em;
  border-top: 0.1rem solid rgba(var(--color-text), 0.18);
  color: rgba(var(--color-text), 0.68);
  font-size: var(--type-x-small);
  line-height: 1.45;
}

.site-footer a {
  color: rgb(var(--color-link));
}

.site-footer__separator {
  display: inline-block;
  margin: 0 0.45em;
}

.info-page {
  max-width: 64rem;
}

.info-page__eyebrow {
  margin: 0 0 1.2em 0;
  font-size: var(--type-small);
}

.info-page__lede {
  margin-top: 1.2em;
  font-size: var(--type-large);
  line-height: 1.35;
}

.info-page__section {
  margin-top: 2.25em;
  padding-top: 1.25em;
  border-top: 0.1rem solid rgba(var(--color-text), 0.2);
}

.info-page__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8em;
  margin-top: 1.4em;
}

.feedback-checklist {
  margin-left: 1.1em;
}

.wb {
  width: 100%;
  margin: 0 auto;
  padding: 1.5em;
  display: grid;
  grid-template-areas: 'header' 'sidebar' 'content';
  grid-template-columns: auto;
}

.intro {
  grid-area: sidebar;
}

.intro__content {
  position: relative;
}

.intro__book-title {
  margin: 0 0 2em 0;
}

.intro__book-title--compact {
  white-space: nowrap;
  font-size: var(--type-small) !important;
  padding: 0.5em 1em !important;
}

.intro__content--sticky {
  position: sticky;
  top: 2em;
}

.intro__utility {
  margin: 0.85em 0 0 0;
}

.intro__back {
  margin: 0;
  font-size: var(--type-small);
}

.intro__masthead {
  margin: 2em 0 0 0;
  padding: 0.5em 0 0 0;
  text-transform: uppercase;
  letter-spacing: 0.3rem;
  font-size: var(--type-xx-small);
}

.intro__title {
  margin: 0.58em 0 0 0;
  font-size: var(--type-xx-large);
  line-height: 1.05;
}

.intro__title a {
  text-decoration: none;
}

.lang-switch {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5em;
  margin: 0.75em 0 0 0;
  font-size: var(--type-x-small);
}

.lang-switch a {
  text-decoration: none;
}

.lang-switch__current {
  font-weight: bold;
  text-decoration: underline;
}

.intro__sections {
  display: none;
  margin: 0.5em 0 0 0;
  padding: 0;
  list-style: none;
}

.intro__sections--index {
  max-height: min(62vh, calc(100vh - 18rem));
  overflow-y: auto;
  padding-right: 0.4em;
}

.intro__sidebar-title {
  margin: 0.55em 0 0 0;
  font-size: var(--type-large);
  line-height: 1.12;
}

.intro__sidebar-title a {
  text-decoration: none;
}

.intro__section {
  margin: 0.28em 0 0 0;
  font-size: var(--type-small);
  font-style: italic;
}

.intro__section a {
  text-decoration: none;
}

.intro__section a.is-active {
  text-decoration: underline;
}

.intro__section--part {
  margin-top: 1em;
  padding-top: 0.8em;
  border-top: 0.1rem solid rgba(var(--color-text), 0.18);
  font-size: var(--type-xx-small);
  font-style: normal;
  font-weight: bold;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.intro__section--part:first-child {
  margin-top: 0;
  padding-top: 0;
  border-top: 0;
}

.intro__section--jump {
  font-style: normal;
  line-height: 1.25;
}

.intro__section--jump a {
  display: block;
}

.intro__next {
  display: none;
  margin: 1.25em 0 0 0;
  font-size: var(--type-small);
}

.intro__next a {
  text-decoration: none;
}

.content {
  margin: 0;
  padding: 0;
  grid-area: content;
  min-width: 0;
  position: relative;
}

.landing-image {
  display: block;
  width: min(100%, 66rem);
  margin: 3em 0 1em 0;
}

.landing-title {
  margin: 0;
  font-size: var(--type-xxx-large);
  line-height: 1.1;
}

.landing-subtitle {
  margin: 0;
  font-size: var(--type-xx-large);
  line-height: 1.2;
}

.landing-author {
  margin: 0;
  font-size: var(--type-small);
  font-style: italic;
}

.toc-part + .toc-part {
  margin-top: 0;
}

.toc-part__title {
  display: block;
  margin: 2em 0 0 0;
  padding: 0.5em 0 0 0;
  border-top: 0.1rem solid rgb(var(--color-text));
}

.toc-part__number {
  margin: 3em 0 0 0;
  text-transform: uppercase;
  letter-spacing: 0.3rem;
  font-size: var(--type-xx-small);
}

.toc-chapters {
  margin: 0;
  padding: 0;
  list-style: none;
}

.toc-chapter {
  margin: 1em 0 1em 0;
  padding: 0 3em 0 0;
}

.toc-chapter__title {
  margin: 0;
  font-size: var(--type-large);
}

.toc-chapter__title a {
  text-decoration: none;
}

.toc-sections {
  margin: 0.5em 0 0 0;
  padding: 0 0 0 0.5em;
  list-style: none;
  border-left: 0.1rem solid rgb(var(--color-link));
}

.toc-sections li {
  margin: 0.2em 0 0;
  font-size: var(--type-small);
  font-style: italic;
}

.chapter h1 {
  margin: 0;
  font-size: var(--type-xx-large);
}

.chapter__header {
  max-width: min(100%, 46em);
  margin: 0 0 1.35em 0;
}

.chapter__label {
  margin: 0 0 0.5em 0;
  text-transform: uppercase;
  letter-spacing: 0.3rem;
  font-size: var(--type-xx-small);
}

.chapter__title {
  margin: 0;
  font-size: var(--type-xx-large);
  line-height: 1.05;
}

.chapter__subtitle {
  margin: 0.35em 0 0 0;
  font-size: var(--type-large);
  line-height: 1.2;
}

.chapter h2 {
  margin-top: 1.6em;
}

.chapter h3 {
  margin-top: 1.3em;
}

.chapter p,
.chapter ul,
.chapter ol,
.chapter blockquote,
.chapter pre,
.chapter table,
.chapter img {
  max-width: min(100%, 46em);
}

.chapter > :first-child {
  margin-top: 0;
}

.translator-credit,
.translator-note {
  max-width: min(100%, 46em);
  color: rgba(0, 0, 0, 0.5);
}

.translator-credit {
  margin-top: 0.45em;
  font-size: var(--type-xx-small);
  letter-spacing: 0.015em;
}

.translator-note {
  margin-top: 0.35em;
  font-size: var(--type-xxx-small);
  line-height: 1.4;
}

.translator-note em {
  font-style: normal;
}

.chapter sup {
  font-size: 0.72em;
  line-height: 0;
  vertical-align: super;
}

.chapter a {
  overflow-wrap: anywhere;
}

.chapter .footnote-ref {
  display: inline;
  margin-left: 0.08em;
  padding: 0;
  border: 0;
  background: none;
  font-size: 1em;
  font-weight: normal;
  line-height: 1;
  text-decoration: none;
}

.chapter .footnote-ref:hover {
  text-decoration: underline;
}

.chapter .footnote {
  max-width: min(100%, 46em);
  margin-top: 2.2em;
  padding-top: 1.1em;
  border-top: 0.1rem solid rgba(0, 0, 0, 0.22);
  font-size: var(--type-x-small);
}

.chapter .footnote hr {
  display: none;
}

.chapter .footnote ol {
  margin: 0.4em 0 0 1.3em;
}

.chapter .footnote li + li {
  margin-top: 0.5em;
}

.chapter .footnote p {
  margin: 0;
  line-height: 1.35;
}

.chapter .footnote-backref {
  margin-left: 0.35em;
  text-decoration: none;
}

[id^="fn:"],
[id^="fnref:"] {
  scroll-margin-top: 7rem;
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1em;
  margin: 0;
  padding: 1em 0 0 0;
}

.pagination__spacer {
  flex: 1 1 auto;
}

.share-selection {
  position: fixed;
  z-index: 50;
  left: 1rem;
  top: 1rem;
  display: none;
  padding: 0.7em 0.9em;
  border: 0.18rem solid rgb(var(--color-link));
  border-radius: 999px;
  background: rgb(var(--color-link));
  color: rgb(var(--color-background));
  font-family: inherit;
  font-size: 1.4rem;
  font-weight: bold;
  line-height: 1;
  box-shadow: 0 0.5rem 1.5rem rgba(0, 0, 0, 0.18);
  cursor: pointer;
}

.share-selection.is-visible {
  display: inline-flex;
}

.mobile-rail {
  margin-bottom: 2em;
}

.mobile-rail .intro__book-title {
  margin: 0;
}

.mobile-rail .intro__masthead {
  margin-top: 1.5em;
}

.mobile-rail .intro__masthead:first-child {
  margin-top: 0;
}

.mobile-rail .intro__sections {
  display: block;
}

@media screen and (min-width: 50em) {
  :root {
    --type-base: calc(0.9em + 0.9vw);
  }

  .wb {
    margin: 0;
    padding: 2em;
    grid-template-areas: 'header header' 'sidebar content';
    grid-template-columns: 0.85fr 2.5fr;
  }

  .intro__book-title {
    margin: 0;
  }

  .intro__sections {
    display: block;
  }

  .content {
    padding: 2.65em clamp(2.5em, 5vw, 5em) 0 3.5em;
  }

  .intro__content {
    top: 2.5em;
    text-align: right;
  }

  .intro__utility {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }

  .lang-switch {
    justify-content: flex-end;
  }

  .intro__next {
    display: block;
  }

  .mobile-rail {
    display: none;
  }
}

@media screen and (min-width: 100em) {
  :root {
    --type-base: 2.75em;
  }

  .wb,
  .root {
    max-width: 250rem;
  }
}

@media (max-width: 960px) {
  :root {
    --type-base: 1.85rem;
  }

  html {
    font-size: 10px;
    -webkit-text-size-adjust: 100%;
    text-size-adjust: 100%;
  }

  body {
    overflow-x: hidden;
  }

  .draft-ribbon {
    top: 0.8rem;
    left: 0.8rem;
    padding: 0.6rem 1rem;
    font-size: 1.1rem;
    box-shadow:
      0.18rem 0.18rem 0 #fff8fb,
      0.38rem 0.38rem 0 #ff9fc4;
  }

  .root {
    width: auto;
    max-width: 64rem;
    margin: 0 auto;
    padding: 1.25em 1.2em 3em;
  }

  .wb {
    width: 100%;
    max-width: 64rem;
    margin: 0 auto;
    padding: 1.25em 1.2em 3em;
  }

  .intro {
    display: none;
  }

  .content {
    width: 100%;
    min-width: 0;
    padding: 0;
  }

  .mobile-rail {
    width: 100%;
    min-width: 0;
  }

  .landing-image,
  .chapter img,
  .chapter p,
  .chapter ul,
  .chapter ol,
  .chapter blockquote,
  .chapter pre,
  .chapter table,
  .chapter__header,
  .translator-credit,
  .translator-note {
    max-width: 100%;
  }

  .chapter table {
    display: block;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .chapter pre {
    max-width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .toc-chapter {
    padding-right: 0;
  }

  .intro__book-title--compact,
  .button {
    white-space: normal;
  }

  .pagination {
    justify-content: flex-start;
  }

  .root__languages {
    flex-direction: column;
  }
}
"""

SCRIPT_JS = """
const sectionLinks = [...document.querySelectorAll('[data-section-link]')];
const headings = sectionLinks
  .map((link) => {
    const id = link.getAttribute('href')?.slice(1);
    return id ? document.getElementById(id) : null;
  })
  .filter(Boolean);

if (sectionLinks.length && headings.length && 'IntersectionObserver' in window) {
  const activeById = new Map(sectionLinks.map((link) => [link.getAttribute('href')?.slice(1), link]));
  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

      if (!visible) return;

      activeById.forEach((link) => link.classList.remove('is-active'));
      const active = activeById.get(visible.target.id);
      if (active) active.classList.add('is-active');
    },
    { rootMargin: '-18% 0px -60% 0px', threshold: [0.1, 0.4, 0.7] }
  );

  headings.forEach((heading) => observer.observe(heading));
}

const readingMeta = document.body.dataset.readingPage;
if (readingMeta) {
  try {
    const saved = JSON.parse(readingMeta);
    if (saved && saved.href && saved.title) {
      const rootHref = saved.href.startsWith('/') ? saved.href : `/${saved.href.replace(/^[/]+/, '')}`;
      localStorage.setItem('broad-book:last-reading', JSON.stringify({ href: rootHref, title: saved.title }));
    }
  } catch (_) {}
}

const continueReadingLink = document.querySelector('[data-continue-reading]');
if (continueReadingLink) {
  try {
    const raw = localStorage.getItem('broad-book:last-reading');
    if (raw) {
      const saved = JSON.parse(raw);
      if (saved && saved.href && saved.title) {
        continueReadingLink.href = saved.href;
        const titleNode = continueReadingLink.querySelector('[data-continue-title]');
        if (titleNode) titleNode.textContent = saved.title;
        continueReadingLink.hidden = false;
        continueReadingLink.classList.add('is-visible');
      }
    }
  } catch (_) {}
}

const chapter = document.querySelector('.chapter');
const shareSelectionButton = document.querySelector('[data-share-selection]');
if (chapter && shareSelectionButton) {
  let selectedText = '';

  const hideShareSelection = () => {
    shareSelectionButton.classList.remove('is-visible');
    shareSelectionButton.setAttribute('aria-hidden', 'true');
  };

  const selectionInsideChapter = (selection) => {
    if (!selection || selection.rangeCount === 0) return false;
    const anchorNode = selection.anchorNode?.nodeType === Node.TEXT_NODE
      ? selection.anchorNode.parentElement
      : selection.anchorNode;
    const focusNode = selection.focusNode?.nodeType === Node.TEXT_NODE
      ? selection.focusNode.parentElement
      : selection.focusNode;
    return Boolean(anchorNode && focusNode && chapter.contains(anchorNode) && chapter.contains(focusNode));
  };

  const showShareSelection = () => {
    const selection = window.getSelection();
    const text = selection?.toString().replace(/[\\s]+/g, ' ').trim() || '';
    if (text.length < 12 || !selectionInsideChapter(selection)) {
      hideShareSelection();
      return;
    }

    selectedText = text.length > 480 ? `${text.slice(0, 477)}...` : text;
    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const left = Math.min(Math.max(rect.left, 12), window.innerWidth - 160);
    const top = Math.max(rect.top - 48, 12);
    shareSelectionButton.style.left = `${left}px`;
    shareSelectionButton.style.top = `${top}px`;
    shareSelectionButton.textContent = shareSelectionButton.dataset.shareLabel || 'Share passage';
    shareSelectionButton.removeAttribute('aria-hidden');
    shareSelectionButton.classList.add('is-visible');
  };

  const shareSelectedText = async () => {
    if (!selectedText) return;
    const url = window.location.href.split('#')[0];
    const text = `"${selectedText}"\n\n${document.title}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: document.title, text, url });
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(`${text}\n${url}`);
        shareSelectionButton.textContent = shareSelectionButton.dataset.copiedLabel || 'Copied';
        window.setTimeout(hideShareSelection, 1200);
      }
    } catch (_) {}
  };

  document.addEventListener('selectionchange', () => window.setTimeout(showShareSelection, 80));
  document.addEventListener('scroll', hideShareSelection, { passive: true });
  shareSelectionButton.addEventListener('click', shareSelectedText);
}
"""


def load_order_file(order_file: Path) -> list[str]:
    files: list[str] = []
    with order_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or re.match(r"^\[.+\]$", line):
                continue
            files.append(line)
    return files


def load_path_map(en_root: Path) -> dict[str, str]:
    path_map_file = en_root / "metadata" / "path_map.json"
    if not path_map_file.exists():
        return {}
    return json.loads(path_map_file.read_text(encoding="utf-8"))


def reverse_path_map(path_map: dict[str, str]) -> dict[str, str]:
    return {target: source for source, target in path_map.items()}


def strip_todo_markdown(md_text: str) -> str:
    # Keep editorial TODOs in the manuscript source, but omit them from the web edition.
    cleaned = re.sub(r"<!--.*?(?:TODO|MEMO).*?-->\s*", "", md_text, flags=re.DOTALL)
    lines = []
    for line in cleaned.splitlines():
        if re.match(r"^\s*(?:TODO|MEMO)[:：].*$", line):
            continue
        line = re.sub(r"\s*\((?:TODO|MEMO)[:：].*?\)", "", line)
        line = re.sub(r"(?:\s+in\s+|\s*)TODO:[^.!?。\n]*(?:[.!?。])?", "", line)
        line = line.replace("TODO chapter", "corresponding chapter")
        line = line.replace("TODO章", "該当章")
        line = re.sub(r"\s{2,}", " ", line).rstrip()
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def render_markdown(md_text: str) -> str:
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "footnotes", "toc", "sane_lists"],
        extension_configs={"toc": {"permalink": False}},
    )
    return linkify_html(md.convert(md_text))


URL_RE = re.compile(r"https?://[^\s<]+")
TRAILING_PUNCTUATION = ".,;:!?)]"
NO_LINKIFY_TAGS = {"a", "code", "pre", "script", "style"}


def trim_trailing_punctuation(url: str) -> tuple[str, str]:
    trailing = ""
    while url and url[-1] in TRAILING_PUNCTUATION:
        ch = url[-1]
        if ch == ")" and url.count("(") >= url.count(")"):
            break
        trailing = ch + trailing
        url = url[:-1]
    return url, trailing


def linkify_text(text: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in URL_RE.finditer(text):
        start, end = match.span()
        url = match.group(0)
        clean_url, trailing = trim_trailing_punctuation(url)
        if not clean_url:
            continue
        parts.append(text[cursor:start])
        escaped_url = html.escape(clean_url, quote=True)
        parts.append(f'<a href="{escaped_url}">{escaped_url}</a>')
        parts.append(trailing)
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


class LinkifyHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.output: list[str] = []
        self.tag_stack: list[str] = []

    def _attrs_to_text(self, attrs: list[tuple[str, str | None]]) -> str:
        rendered = []
        for key, value in attrs:
            if value is None:
                rendered.append(f" {key}")
            else:
                rendered.append(f' {key}="{html.escape(value, quote=True)}"')
        return "".join(rendered)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.output.append(f"<{tag}{self._attrs_to_text(attrs)}>")
        self.tag_stack.append(tag.lower())

    def handle_endtag(self, tag: str) -> None:
        self.output.append(f"</{tag}>")
        if self.tag_stack:
            self.tag_stack.pop()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.output.append(f"<{tag}{self._attrs_to_text(attrs)} />")

    def handle_data(self, data: str) -> None:
        in_non_linkified_context = any(tag in NO_LINKIFY_TAGS for tag in self.tag_stack)
        self.output.append(data if in_non_linkified_context else linkify_text(data))

    def handle_entityref(self, name: str) -> None:
        self.output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.output.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.output.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.output.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.output.append(f"<?{data}>")


def linkify_html(html_text: str) -> str:
    parser = LinkifyHTMLParser()
    parser.feed(html_text)
    parser.close()
    return "".join(parser.output)


def strip_tags(fragment: str) -> str:
    return re.sub(r"<[^>]+>", "", fragment).strip()


class G0VWordmarkHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.output: list[str] = []
        self.tag_stack: list[str] = []

    def _attrs_to_text(self, attrs: list[tuple[str, str | None]]) -> str:
        rendered = []
        for key, value in attrs:
            if value is None:
                rendered.append(f" {key}")
            else:
                rendered.append(f' {key}="{html.escape(value, quote=True)}"')
        return "".join(rendered)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.output.append(f"<{tag}{self._attrs_to_text(attrs)}>")
        self.tag_stack.append(tag.lower())

    def handle_endtag(self, tag: str) -> None:
        self.output.append(f"</{tag}>")
        if self.tag_stack:
            self.tag_stack.pop()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.output.append(f"<{tag}{self._attrs_to_text(attrs)} />")

    def handle_data(self, data: str) -> None:
        if any(tag in {"a", "code", "pre", "script", "style"} for tag in self.tag_stack):
            self.output.append(data)
            return
        data = re.sub(r'(?<![\\w])g0v\\.tw(?![\\w])', r'<span class="wordmark-inline">g0v.tw</span>', data)
        data = re.sub(r'(?<![\\w])gov\\.tw(?![\\w])', r'<span class="wordmark-inline">gov.tw</span>', data)
        data = re.sub(r'(?<![\\w])g0v(?![\\w])', r'<span class="wordmark-inline">g0v</span>', data)
        self.output.append(data)

    def handle_entityref(self, name: str) -> None:
        self.output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.output.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.output.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.output.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.output.append(f"<?{data}>")


def style_g0v_wordmark(html_text: str) -> str:
    parser = G0VWordmarkHTMLParser()
    parser.feed(html_text)
    parser.close()
    return "".join(parser.output)


def first_heading(md_text: str) -> str:
    for line in md_text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if match:
            return match.group(2).strip()
    return "Untitled"


def chapter_number(source_rel: str) -> int | None:
    match = re.match(r"^(\d{2})_", Path(source_rel).name)
    if not match:
        return None
    return int(match.group(1))


def part_label_for_file(source_rel: str, config: LanguageConfig) -> str:
    number = chapter_number(source_rel)
    if number is None:
        return config.part_labels[1][1]
    for (start, end), label in config.part_labels:
        if start <= number <= end:
            return label
    return config.part_labels[1][1]


def chapter_label_for_file(source_rel: str, title: str, config: LanguageConfig) -> str:
    ui = LANGUAGE_UI[config.code]
    if source_rel.startswith("column/"):
        return ui["column"]

    number = chapter_number(source_rel)
    if number == 0:
        if "audrey" in source_rel.lower():
            return ui["endorsement"]
        return ui["preface"]
    if number == 99:
        return ui["appendix"]
    if number is None:
        return ui["column"] if "column" in title.lower() else ui["chapter"]

    if config.code == "ja":
        return f"第{number}章"
    return f"Chapter {number}"


def output_html_rel(relative_markdown_path: str) -> str:
    return str(Path(relative_markdown_path).with_suffix(".html").as_posix())


def relative_href(from_rel: str, to_rel: str) -> str:
    return os.path.relpath(to_rel, start=Path(from_rel).parent).replace(os.sep, "/")


def fix_relative_assets(
    html_text: str,
    repo_root: Path,
    output_root: Path,
    source_root: Path,
    source_path: Path,
    output_path: Path,
    markdown_map: dict[str, str],
) -> str:
    translated_sibling_root: Path | None = None
    try:
        translated_sibling_root = repo_root / source_path.relative_to(source_root).parent
    except ValueError:
        translated_sibling_root = None

    def rewrite(match: re.Match[str]) -> str:
        attr = match.group(1)
        raw_target = match.group(2)
        if raw_target.startswith(("http://", "https://", "mailto:", "#", "data:")):
            return match.group(0)

        target, sep, anchor = raw_target.partition("#")

        if attr == "href" and target.endswith(".md"):
            normalized = Path(target).as_posix()
            if normalized in markdown_map:
                return f'{attr}="{markdown_map[normalized]}{sep}{anchor}"'

            local_target = (source_path.parent / target).resolve()
            try:
                local_rel = local_target.relative_to(source_root.resolve()).as_posix()
            except ValueError:
                local_rel = ""
            if local_rel and local_rel in markdown_map:
                return f'{attr}="{markdown_map[local_rel]}{sep}{anchor}"'

        local_candidate = (source_path.parent / target).resolve()
        translated_sibling_candidate = (
            (translated_sibling_root / target).resolve()
            if translated_sibling_root is not None
            else None
        )
        fallback_candidate = (repo_root / target).resolve()
        if local_candidate.exists():
            resolved = local_candidate
        elif translated_sibling_candidate is not None and translated_sibling_candidate.exists():
            resolved = translated_sibling_candidate
        else:
            resolved = fallback_candidate

        rewritten = target
        if resolved.exists():
            try:
                repo_rel = resolved.relative_to(repo_root.resolve()).as_posix()
            except ValueError:
                repo_rel = ""

            published_candidate = output_root / repo_rel if repo_rel else None
            if published_candidate is not None and published_candidate.exists():
                current_output_rel = output_path.relative_to(output_root).as_posix()
                rewritten = relative_href(current_output_rel, repo_rel)
            else:
                rewritten = os.path.relpath(resolved, start=output_path.parent.resolve()).replace(os.sep, "/")
        return f'{attr}="{rewritten}{sep}{anchor}"'

    return re.sub(r'(src|href)="([^"]+)"', rewrite, html_text)


def extract_headings(html_text: str) -> list[tuple[str, str]]:
    headings: list[tuple[str, str]] = []
    for match in re.finditer(r"<h2 id=\"([^\"]+)\">(.*?)</h2>", html_text, flags=re.DOTALL):
        headings.append((match.group(1), strip_tags(match.group(2))))
    return headings


def strip_leading_heading(html_text: str) -> str:
    return re.sub(r"^\s*<h[1-2][^>]*>.*?</h[1-2]>\s*", "", html_text, count=1, flags=re.DOTALL)


def soften_translator_meta(html_text: str) -> str:
    note_html = f'<p class="translator-note"><em>{html.escape(TRANSLATION_NOTE_TEXT)}</em></p>'
    html_text = re.sub(
        r"<p>English translation by (.*?)</p>",
        r'<p class="translator-credit">English translation by \1</p>',
        html_text,
        count=1,
        flags=re.DOTALL,
    )
    html_text = re.sub(
        r"<p><em>Translation note \(English edition\):.*?</em></p>",
        note_html,
        html_text,
        flags=re.DOTALL,
    )
    if 'class="translator-credit"' in html_text and 'class="translator-note"' not in html_text:
        html_text = re.sub(
            r'(<p class="translator-credit">.*?</p>)',
            rf"\1\n{note_html}",
            html_text,
            count=1,
            flags=re.DOTALL,
        )
    html_text = re.sub(
        r'(<p class="translator-note"><em>.*?</em></p>\s*)(<p class="translator-credit">.*?</p>)',
        r"\2\n\1",
        html_text,
        count=1,
        flags=re.DOTALL,
    )
    return html_text


def sidebar_chapter_title(chapter: Chapter) -> str:
    pattern = rf"^{re.escape(chapter.chapter_label)}(?:\s*[:：-]\s*|\s+)"
    return re.sub(pattern, "", chapter.title, count=1).strip() or chapter.title


def split_display_title(title_text: str) -> tuple[str, str]:
    parts = re.split(r"\s*[—–]\s*|\s-\s", title_text, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return title_text, ""


def sidebar_display_title(chapter: Chapter, config: LanguageConfig) -> str:
    title_text = sidebar_chapter_title(chapter)
    if config.code != "en":
        return title_text
    main_title, _ = split_display_title(title_text)
    return main_title


def sidebar_section_headings(chapter: Chapter) -> list[tuple[str, str]]:
    headings = list(chapter.headings)
    if headings and headings[0][1].strip() == sidebar_chapter_title(chapter):
        return headings[1:]
    return headings


def chapter_link_label(chapter: Chapter) -> str:
    if chapter.title.lower().startswith(chapter.chapter_label.lower()):
        return chapter.title
    return f"{chapter.chapter_label}: {chapter.title}"


def index_anchor_id(chapter: Chapter) -> str:
    stem = Path(chapter.output_rel).with_suffix("").as_posix()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()
    return f"index-jump-{slug}"


def index_jump_label(chapter: Chapter, config: LanguageConfig) -> str:
    title_text = sidebar_display_title(chapter, config)
    if chapter.chapter_label in {
        LANGUAGE_UI[config.code]["preface"],
        LANGUAGE_UI[config.code]["endorsement"],
        LANGUAGE_UI[config.code]["column"],
        LANGUAGE_UI[config.code]["appendix"],
    }:
        return title_text
    separator = ": " if config.code == "en" else " "
    return f"{chapter.chapter_label}{separator}{title_text}"


def build_chapters(
    repo_root: Path,
    output_root: Path,
    config: LanguageConfig,
    canonical_map: dict[str, str],
) -> list[Chapter]:
    files = load_order_file(config.order_file)
    markdown_map = {relative_path: output_html_rel(relative_path) for relative_path in files}

    chapters: list[Chapter] = []
    current_part = config.part_labels[0][1]

    for relative_path in files:
        source_path = config.source_root / relative_path
        if not source_path.exists() or source_path.suffix != ".md":
            continue

        output_rel = output_html_rel(relative_path)
        output_path = output_root / config.code / output_rel
        md_text = source_path.read_text(encoding="utf-8")
        filtered_md_text = strip_todo_markdown(md_text)
        title = first_heading(filtered_md_text)
        number = chapter_number(relative_path)
        if number is not None:
            current_part = part_label_for_file(relative_path, config)

        html_body = render_markdown(filtered_md_text)
        if config.code == "en":
            html_body = soften_translator_meta(html_body)
        if config.code == "en" and relative_path in {"11_01_taiwan.md", "11_05_harnessing_connective_action.md"}:
            html_body = style_g0v_wordmark(html_body)
        html_body = fix_relative_assets(
            html_text=html_body,
            repo_root=repo_root,
            output_root=output_root,
            source_root=config.source_root,
            source_path=source_path,
            output_path=output_path,
            markdown_map=markdown_map,
        )

        chapters.append(
            Chapter(
                source_rel=relative_path,
                output_rel=output_rel,
                canonical_rel=canonical_map.get(relative_path, relative_path),
                part_label=current_part,
                chapter_label=chapter_label_for_file(relative_path, title, config),
                title=title,
                headings=extract_headings(html_body),
                body_html=html_body,
            )
        )

    return chapters


def build_language_targets(sites: dict[str, list[Chapter]]) -> dict[str, dict[str, str]]:
    targets: dict[str, dict[str, str]] = {}
    for lang_code, chapters in sites.items():
        for chapter in chapters:
            targets.setdefault(chapter.canonical_rel, {})[lang_code] = (
                f"{lang_code}/{chapter.output_rel}"
            )
    return targets


def render_language_switch(
    current_page_rel: str,
    current_lang: str,
    configs: list[LanguageConfig],
    language_targets: dict[str, dict[str, str]],
    canonical_rel: str | None,
) -> str:
    parts = []
    for config in configs:
        if canonical_rel is None:
            target = f"{config.code}/index.html"
        else:
            target = language_targets.get(canonical_rel, {}).get(config.code) or f"{config.code}/index.html"

        if config.code == current_lang:
            parts.append(f'<span class="lang-switch__current">{html.escape(config.label)}</span>')
        else:
            parts.append(
                f'<a href="{relative_href(current_page_rel, target)}">{html.escape(config.label)}</a>'
            )
    return f'<div class="lang-switch">{" ".join(parts)}</div>'


def render_site_footer(current_page_rel: str, lang_code: str = "en") -> str:
    ui = LANGUAGE_UI.get(lang_code, LANGUAGE_UI["en"])
    about_target = f"{lang_code}/about.html"
    feedback_target = f"{lang_code}/feedback.html"
    if current_page_rel == "about.html":
        about_target = "about.html"
    if current_page_rel == "feedback.html":
        feedback_target = "feedback.html"
    about_href = relative_href(current_page_rel, about_target)
    feedback_href = relative_href(current_page_rel, feedback_target)
    return f"""
        <footer class="site-footer">
          <a href="{about_href}">{html.escape(ui["about_this_book"])}</a>
          <span class="site-footer__separator" aria-hidden="true">/</span>
          <a href="{feedback_href}">{html.escape(ui["report_problem"])}</a>
        </footer>
"""


def page_template(
    *,
    title: str,
    lang_attr: str,
    assets_href: str,
    body: str,
    body_class: str,
) -> str:
    badge_label = (
        LANGUAGE_UI["ja"]["draft_badge"]
        if lang_attr == "ja"
        else f'{LANGUAGE_UI["en"]["draft_badge"]} / {LANGUAGE_UI["ja"]["draft_badge"]}'
    )
    return f"""<!doctype html>
<html lang="{lang_attr}">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)}</title>
    <meta name="description" content="Broad Listening web book">
    <link rel="stylesheet" href="{SHAPE_UP_TYPEKIT_CSS}">
    <link rel="stylesheet" href="{assets_href}">
  </head>
  <body class="{body_class}">
    {DESIGN_CREDIT_COMMENT}
    <div class="draft-ribbon" aria-label="{html.escape(badge_label)}">
      <span class="draft-ribbon__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 1.8l1.9 5.1 5.1 1.9-5.1 1.9-1.9 5.1-1.9-5.1-5.1-1.9 5.1-1.9L12 1.8zm6.6 12.8.9 2.5 2.5.9-2.5.9-.9 2.5-.9-2.5-2.5-.9 2.5-.9.9-2.5zm-12.7.8.7 1.9 1.9.7-1.9.7-.7 1.9-.7-1.9-1.9-.7 1.9-.7.7-1.9z"/>
        </svg>
      </span>
      <span class="draft-ribbon__text">{html.escape(badge_label)}</span>
      <span class="draft-ribbon__icon draft-ribbon__icon--heart" aria-hidden="true">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 21.2l-1.4-1.3C5.2 15 2 12.1 2 8.5 2 5.9 4 4 6.5 4c1.4 0 2.9.7 3.8 1.9C11.3 4.7 12.8 4 14.2 4 16.8 4 18.8 5.9 18.8 8.5c0 3.6-3.2 6.5-8.6 11.4L12 21.2z"/>
        </svg>
      </span>
    </div>
    {body}
    <script src="{assets_href.replace('book.css', 'book.js')}"></script>
  </body>
</html>
"""


def render_root_index(repo_root: Path, output_root: Path, configs: list[LanguageConfig]) -> str:
    english = next(config for config in configs if config.code == "en")
    image_href = relative_href("index.html", LANDING_IMAGE)
    buttons = []
    for config in configs:
        cta = "Start reading in English" if config.code == "en" else "日本語で読み始める"
        buttons.append(
            f"""
        <p class="root__language"><a class="button" href="{config.code}/index.html">{html.escape(cta)}</a></p>
"""
        )

    body = f"""
    <div class="root">
      <main class="root__main">
        <img class="landing-image" src="{image_href}" alt="Broad listening diagram">
        <h1 class="root__title">{html.escape(english.title)}</h1>
        <p class="root__subtitle">{html.escape(english.subtitle)}</p>
        <div class="root__languages">
          {''.join(buttons)}
        </div>
        <p><a class="button button--ghost" href="en/about.html">About this Book</a></p>
        <p><a class="button button--ghost continue-reading" data-continue-reading hidden href="en/index.html"><span><span class="continue-reading__eyebrow">Continue reading</span><span class="continue-reading__title" data-continue-title>Pick up where you left off</span></span><span class="continue-reading__arrow">→</span></a></p>
        <section class="root__notes">
          <h2 class="root__notes-title">With Thanks</h2>
          <p>With gratitude to the <a href="{DD2030_URL}">Digital Democracy 2030 team</a> for creating and sharing the source material behind this web edition.</p>
          <p>The manuscript and generated site code are available on <a href="{SOURCE_REPO_URL}">GitHub</a>, and this edition is published under the <a href="{LICENSE_URL}">CC BY 4.0</a> license.</p>
        </section>
        {render_site_footer("index.html", "en")}
      </main>
    </div>
"""
    return page_template(
        title="Broad Listening",
        lang_attr="en",
        assets_href="./assets/book.css",
        body=body,
        body_class="lang-en",
    )


def render_about_page(config: LanguageConfig, current_page_rel: str) -> str:
    ui = LANGUAGE_UI[config.code]
    assets_href = relative_href(current_page_rel, "assets/book.css")
    back_href = relative_href(current_page_rel, f"{config.code}/index.html")

    if config.code == "ja":
        body = f"""
    <div class="root info-page">
      <main class="root__main">
        <p class="info-page__eyebrow"><a href="{back_href}"><em>{html.escape(ui["back_to_edition"])}</em></a></p>
        <h1 class="root__title">この本について</h1>
        <p class="info-page__lede">
          <em>選挙を変えたブロードリスニング</em>は、
          <a href="{DD2030_URL}">Digital Democracy 2030</a> コミュニティによる書籍です。
          生成AIが、大規模な声の収集・分析・民主的な参加をどのように支えられるかを共有するために公開されています。
        </p>
        <section class="info-page__section">
          <h2>著者と翻訳</h2>
          <p>
            本書の著者は <a href="{DD2030_URL}">Digital Democracy 2030 コミュニティ</a>です。
            英語翻訳とこのウェブサイトは <a href="https://x.com/lukec">@lukec</a> がリードし、
            より多くの読者が読み、確認し、改善できるようにしています。
          </p>
          <p>
            元の原稿は <a href="{SOURCE_REPO_URL}">GitHub</a> で公開されています。
            このウェブ版は <a href="{LICENSE_URL}">CC BY 4.0</a> ライセンスで公開されています。
          </p>
        </section>
        <section class="info-page__section">
          <h2>協力するには</h2>
          <p>
            誤字、リンク切れ、翻訳の問題、レイアウトの問題、事実関係の懸念などを見つけた場合は、
            GitHub Issue で具体的に報告してください。具体的な報告ほど確認と修正がしやすくなります。
          </p>
          <p class="info-page__actions">
            <a class="button" href="{relative_href(current_page_rel, "ja/index.html")}">日本語版を読む</a>
            <a class="button button--ghost" href="{relative_href(current_page_rel, "ja/feedback.html")}">本の問題を報告する</a>
          </p>
        </section>
        {render_site_footer(current_page_rel, config.code)}
      </main>
    </div>
"""
        title = "この本について | 選挙を変えたブロードリスニング"
    else:
        body = f"""
    <div class="root info-page">
      <main class="root__main">
        <p class="info-page__eyebrow"><a href="{back_href}"><em>{html.escape(ui["back_to_edition"])}</em></a></p>
        <h1 class="root__title">About this Book</h1>
        <p class="info-page__lede">
          <em>Broad Listening</em> is a community-authored book from
          <a href="{DD2030_URL}">Digital Democracy 2030</a>, shared to help more people understand
          how generative AI can support large-scale listening, public-opinion analysis, and democratic participation.
        </p>
        <section class="info-page__section">
          <h2>Authorship and translation</h2>
          <p>
            The <a href="{DD2030_URL}">Digital Democracy 2030 community</a> is the author of this book.
            The English translation and this website are led by <a href="https://x.com/lukec">@lukec</a> so the work can be read, checked,
            and improved by a broader English-speaking audience.
          </p>
          <p>
            The original manuscript remains available on <a href="{SOURCE_REPO_URL}">GitHub</a>.
            This web edition is published under the <a href="{LICENSE_URL}">CC BY 4.0</a> license.
          </p>
        </section>
        <section class="info-page__section">
          <h2>How to help</h2>
          <p>
            If you find a typo, broken link, mistranslation, layout issue, or factual problem, please report it
            as a structured GitHub Issue. Specific reports are much easier to review and fix.
          </p>
          <p class="info-page__actions">
            <a class="button" href="{relative_href(current_page_rel, "en/index.html")}">Read the English edition</a>
            <a class="button button--ghost" href="{relative_href(current_page_rel, "en/feedback.html")}">Problems with the book?</a>
          </p>
        </section>
        {render_site_footer(current_page_rel, config.code)}
      </main>
    </div>
"""
        title = "About this Book | Broad Listening"

    return page_template(
        title=title,
        lang_attr=config.lang_attr,
        assets_href=assets_href,
        body=body,
        body_class=config.body_class,
    )


def render_feedback_page(config: LanguageConfig, current_page_rel: str) -> str:
    ui = LANGUAGE_UI[config.code]
    assets_href = relative_href(current_page_rel, "assets/book.css")
    back_href = relative_href(current_page_rel, f"{config.code}/index.html")

    if config.code == "ja":
        body = f"""
    <div class="root info-page">
      <main class="root__main">
        <p class="info-page__eyebrow"><a href="{back_href}"><em>{html.escape(ui["back_to_edition"])}</em></a></p>
        <h1 class="root__title">本の問題を報告する</h1>
        <p class="info-page__lede">
          本やウェブサイトの具体的な問題は GitHub Issues で報告してください。
          具体的で確認しやすい報告ほど、レビューと修正がしやすくなります。
        </p>
        <section class="info-page__section">
          <h2>役に立つ Issue の書き方</h2>
          <ul class="feedback-checklist">
            <li>問題があるページの正確な URL。</li>
            <li>該当する文、見出し、画像、表、リンク。</li>
            <li>何が問題に見えるか、期待する状態は何か。</li>
            <li>翻訳の問題であれば、英語の該当箇所と、可能なら日本語原文。</li>
            <li>サイトの問題であれば、ブラウザ、端末、必要に応じてスクリーンショット。</li>
          </ul>
          <p class="info-page__actions">
            <a class="button" href="{SITE_NEW_ISSUE_URL}">GitHub Issue を作成する</a>
            <a class="button button--ghost" href="{SITE_ISSUES_URL}">既存の Issue を見る</a>
          </p>
        </section>
        <section class="info-page__section">
          <h2>新しい Issue を作る前に</h2>
          <p>
            同じ問題がすでに報告されていないか、簡単に確認してください。
            既存の Issue がある場合は、新しく作るのではなく不足している情報を追加してください。
          </p>
        </section>
        {render_site_footer(current_page_rel, config.code)}
      </main>
    </div>
"""
        title = "本の問題を報告する | 選挙を変えたブロードリスニング"
    else:
        body = f"""
    <div class="root info-page">
      <main class="root__main">
        <p class="info-page__eyebrow"><a href="{back_href}"><em>{html.escape(ui["back_to_edition"])}</em></a></p>
        <h1 class="root__title">Problems with the book?</h1>
        <p class="info-page__lede">
          Please use GitHub Issues to report concrete problems with the book or this website.
          Useful issues are specific, checkable, and include enough context for someone else to reproduce or review.
        </p>
        <section class="info-page__section">
          <h2>What makes a useful issue</h2>
          <ul class="feedback-checklist">
            <li>The exact page URL.</li>
            <li>The sentence, heading, image, table, or link involved.</li>
            <li>What seems wrong and what you expected instead.</li>
            <li>For translation issues, include the English passage and, if possible, the Japanese source passage.</li>
            <li>For site issues, include your browser, device, and a screenshot when helpful.</li>
          </ul>
          <p class="info-page__actions">
            <a class="button" href="{SITE_NEW_ISSUE_URL}">Open a GitHub Issue</a>
            <a class="button button--ghost" href="{SITE_ISSUES_URL}">View existing issues</a>
          </p>
        </section>
        <section class="info-page__section">
          <h2>Before opening a new issue</h2>
          <p>
            Please quickly check whether the same problem has already been reported.
            If it has, add any missing detail to the existing issue instead of creating a duplicate.
          </p>
        </section>
        {render_site_footer(current_page_rel, config.code)}
      </main>
    </div>
"""
        title = "Problems with the Book | Broad Listening"

    return page_template(
        title=title,
        lang_attr=config.lang_attr,
        assets_href=assets_href,
        body=body,
        body_class=config.body_class,
    )


def render_index(
    *,
    repo_root: Path,
    output_root: Path,
    config: LanguageConfig,
    chapters: list[Chapter],
    configs: list[LanguageConfig],
    language_targets: dict[str, dict[str, str]],
) -> str:
    ui = LANGUAGE_UI[config.code]
    current_page_rel = f"{config.code}/index.html"
    image_href = relative_href(current_page_rel, LANDING_IMAGE)
    grouped: list[tuple[str, list[Chapter]]] = []
    for chapter in chapters:
        if not grouped or grouped[-1][0] != chapter.part_label:
            grouped.append((chapter.part_label, [chapter]))
        else:
            grouped[-1][1].append(chapter)

    jump_groups = []
    for part_label, part_chapters in grouped:
        jump_items = "".join(
            f'<li class="intro__section intro__section--jump"><a data-section-link href="#{index_anchor_id(chapter)}">{html.escape(index_jump_label(chapter, config))}</a></li>'
            for chapter in part_chapters
        )
        jump_groups.append(
            f"""
          <li class="intro__section intro__section--part">{html.escape(part_label)}</li>
          {jump_items}
"""
        )

    sidebar = f"""
      <aside class="intro">
        <div class="intro__content intro__content--sticky">
          <a class="intro__book-title button intro__book-title--compact" href="{relative_href(current_page_rel, f"{config.code}/index.html")}">{html.escape(config.title)}</a>
          <div class="intro__utility">
            <p class="intro__back"><a href="{relative_href(current_page_rel, 'index.html')}"><em>{html.escape(ui["all_languages"])}</em></a></p>
            {render_language_switch(current_page_rel, config.code, configs, language_targets, None)}
          </div>
          <p class="intro__masthead">{html.escape(ui["chapters_in_language"])}</p>
          <ul class="intro__sections intro__sections--index">
            {''.join(jump_groups)}
          </ul>
        </div>
      </aside>
"""

    parts = []
    for part_label, part_chapters in grouped:
        items = []
        for chapter in part_chapters:
            sections = "".join(
                f'<li><a href="{chapter.output_rel}#{heading_id}">{html.escape(label)}</a></li>'
                for heading_id, label in chapter.headings[:8]
            )
            chapter_number_html = (
                f'<p class="toc-part__number">{html.escape(chapter.chapter_label)}</p>'
                if chapter.chapter_label not in {
                    ui["preface"],
                    ui["endorsement"],
                    ui["column"],
                    ui["appendix"],
                }
                else ""
            )
            items.append(
                f"""
        <li class="toc-chapter" id="{index_anchor_id(chapter)}">
          {chapter_number_html}
          <h3 class="toc-chapter__title"><a href="{chapter.output_rel}">{html.escape(chapter.title)}</a></h3>
          {"<ul class=\"toc-sections\">" + sections + "</ul>" if sections else ""}
        </li>
"""
            )

        title_class = "toc-part__title"
        if part_label == config.part_labels[0][1]:
            title_class += " sr-only"
        parts.append(
            f"""
      <section class="toc-part">
        <h2 class="{title_class}">{html.escape(part_label)}</h2>
        <ul class="toc-chapters">
          {''.join(items)}
        </ul>
      </section>
"""
        )

    body = f"""
    <main class="wb">
      {sidebar}

      <section class="content">
        <img class="landing-image" src="{image_href}" alt="Broad listening diagram">
        <h1 class="landing-title">{html.escape(config.title)}</h1>
        <p class="landing-subtitle">{config.subtitle}</p>
        <p class="landing-author"><em>{html.escape(config.author)}</em></p>
        <p><a class="button" href="{chapters[0].output_rel}">{html.escape(ui["start_reading"])}</a></p>
        <p><a class="button button--ghost continue-reading" data-continue-reading hidden href="{chapters[0].output_rel}"><span><span class="continue-reading__eyebrow">{html.escape(ui['continue_reading_short'])}</span><span class="continue-reading__title" data-continue-title>{html.escape(chapters[0].title)}</span></span><span class="continue-reading__arrow">→</span></a></p>
        <hr>
        {''.join(parts)}
        {render_site_footer(current_page_rel, config.code)}
      </section>
    </main>
"""
    assets_href = relative_href(current_page_rel, "assets/book.css")
    return page_template(
        title=f"{config.title} | {ui['site_suffix']}",
        lang_attr=config.lang_attr,
        assets_href=assets_href,
        body=body,
        body_class=config.body_class,
    )


def render_sidebar(
    *,
    current_page_rel: str,
    config: LanguageConfig,
    configs: list[LanguageConfig],
    chapter: Chapter,
    language_targets: dict[str, dict[str, str]],
    next_href: str,
    next_title: str,
) -> str:
    ui = LANGUAGE_UI[config.code]
    headings = sidebar_section_headings(chapter)
    section_items = "".join(
        f'<li class="intro__section"><a data-section-link href="#{heading_id}">{html.escape(label)}</a></li>'
        for heading_id, label in headings
    )
    title_text = sidebar_display_title(chapter, config)
    sidebar_next = (
        f'<p class="intro__next"><a href="{next_href}">{html.escape(ui["next_prefix"])} {html.escape(next_title)}</a></p>'
        if next_href and next_title
        else ""
    )
    sidebar_title = (
        f'<h2 class="intro__sidebar-title"><a href="{relative_href(current_page_rel, current_page_rel)}">{html.escape(title_text)}</a></h2>'
        if config.code == "en" and title_text != sidebar_chapter_title(chapter)
        else ""
    )

    return f"""
      <aside class="intro">
        <div class="intro__content intro__content--sticky">
          <a class="intro__book-title button intro__book-title--compact" href="{relative_href(current_page_rel, f"{config.code}/index.html")}">{html.escape(config.title)}</a>
          <div class="intro__utility">
            <p class="intro__back"><a href="{relative_href(current_page_rel, 'index.html')}"><em>{html.escape(LANGUAGE_UI[config.code]["all_languages"])}</em></a></p>
            {render_language_switch(current_page_rel, config.code, configs, language_targets, chapter.canonical_rel)}
          </div>
          <p class="intro__masthead">{html.escape(chapter.chapter_label)}</p>
          {sidebar_title}
          <ul class="intro__sections">{section_items}</ul>
          {sidebar_next}
        </div>
      </aside>
"""


def render_mobile_rail(
    *,
    current_page_rel: str,
    config: LanguageConfig,
    configs: list[LanguageConfig],
    chapter: Chapter,
    language_targets: dict[str, dict[str, str]],
) -> str:
    headings = sidebar_section_headings(chapter)
    section_items = "".join(
        f'<li class="intro__section"><a data-section-link href="#{heading_id}">{html.escape(label)}</a></li>'
        for heading_id, label in headings
    )
    title_text = sidebar_display_title(chapter, config)
    sidebar_title = (
        f'<h2 class="intro__sidebar-title"><a href="{relative_href(current_page_rel, current_page_rel)}">{html.escape(title_text)}</a></h2>'
        if config.code == "en" and title_text != sidebar_chapter_title(chapter)
        else ""
    )

    return f"""
      <div class="mobile-rail">
          <a class="intro__book-title button intro__book-title--compact" href="{relative_href(current_page_rel, f"{config.code}/index.html")}">{html.escape(config.title)}</a>
          <div class="intro__utility">
            <p class="intro__back"><a href="{relative_href(current_page_rel, 'index.html')}"><em>{html.escape(LANGUAGE_UI[config.code]["all_languages"])}</em></a></p>
          </div>
          {render_language_switch(current_page_rel, config.code, configs, language_targets, chapter.canonical_rel)}
          <p class="intro__masthead">{html.escape(chapter.chapter_label)}</p>
          {sidebar_title}
          <ul class="intro__sections">{section_items}</ul>
      </div>
"""


def render_chapter_page(
    *,
    current_page_rel: str,
    config: LanguageConfig,
    configs: list[LanguageConfig],
    chapter: Chapter,
    all_chapters: list[Chapter],
    language_targets: dict[str, dict[str, str]],
    previous_href: str,
    next_href: str,
) -> str:
    ui = LANGUAGE_UI[config.code]
    reading_meta = html.escape(json.dumps({"href": current_page_rel, "title": chapter.title}), quote=True)
    body_html = strip_leading_heading(chapter.body_html)
    title_text = sidebar_chapter_title(chapter)
    display_title, display_subtitle = split_display_title(title_text) if config.code == "en" else (title_text, "")
    next_title = ""
    if next_href:
        next_title = sidebar_display_title(all_chapters[all_chapters.index(chapter) + 1], config)

    footer_left = (
        f'<a class="button button--ghost" href="{previous_href}">{html.escape(ui["previous_chapter"])}</a>'
        if previous_href
        else '<span class="pagination__spacer"></span>'
    )
    footer_right = (
        f'<a class="button" href="{next_href}">{html.escape(ui["next_chapter"])}</a>'
        if next_href
        else f'<a class="button" href="{relative_href(current_page_rel, f"{config.code}/index.html")}">{html.escape(ui["back_to_contents"])}</a>'
    )

    body = f"""
    <main class="wb">
      {render_sidebar(
          current_page_rel=current_page_rel,
          config=config,
          configs=configs,
          chapter=chapter,
          language_targets=language_targets,
          next_href=next_href,
          next_title=next_title,
      )}
      <section class="content chapter">
        {render_mobile_rail(
            current_page_rel=current_page_rel,
            config=config,
            configs=configs,
            chapter=chapter,
            language_targets=language_targets,
        )}
        <header class="chapter__header">
          <p class="chapter__label">{html.escape(chapter.chapter_label)}</p>
          <h1 class="chapter__title">{html.escape(display_title)}</h1>
          {f'<p class="chapter__subtitle">{html.escape(display_subtitle)}</p>' if display_subtitle else ""}
        </header>
        {body_html}
        <nav class="pagination">
          {footer_left}
          {footer_right}
        </nav>
        {render_site_footer(current_page_rel, config.code)}
        <button
          class="share-selection"
          type="button"
          data-share-selection
          data-share-label="{html.escape(ui["share_passage"])}"
          data-copied-label="{html.escape(ui["copied_passage"])}"
          aria-hidden="true"
        >{html.escape(ui["share_passage"])}</button>
      </section>
    </main>
"""
    assets_href = relative_href(current_page_rel, "assets/book.css")
    return page_template(
        title=f"{chapter.title} | {config.title}",
        lang_attr=config.lang_attr,
        assets_href=assets_href,
        body=body,
        body_class=config.body_class,
    ).replace(f'<body class="{config.body_class}">', f'<body class="{config.body_class}" data-reading-page="{reading_meta}">')


def sync_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    for path in source.rglob("*"):
        rel = path.relative_to(source)
        target = destination / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def build_site(repo_root: Path, output_root: Path) -> list[Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    assets_dir = output_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "book.css").write_text(STYLE_CSS.strip() + "\n", encoding="utf-8")
    (assets_dir / "book.js").write_text(SCRIPT_JS.strip() + "\n", encoding="utf-8")
    sync_tree(repo_root / "images", output_root / "images")

    en_root = repo_root / "en"
    path_map = load_path_map(en_root)
    reverse_map = reverse_path_map(path_map)

    configs = [
        LanguageConfig(
            code="ja",
            lang_attr="ja",
            title="選挙を変えたブロードリスニング",
            subtitle="生成AIが実現する民意の可視化と分析",
            author="Digital Democracy 2030",
            source_root=repo_root,
            order_file=repo_root / "book_order.txt",
            label="日本語",
            edition_label="日本語版",
            body_class="lang-ja",
            part_labels=[
                ((0, 0), "序文"),
                ((1, 3), "第1部：ブロードリスニングとは何か"),
                ((4, 11), "第2部：事例紹介"),
                ((12, 13), "第3部：技術編"),
                ((99, 99), "付録"),
            ],
        ),
        LanguageConfig(
            code="en",
            lang_attr="en",
            title="Broad Listening",
            subtitle="Understanding Public Opinion at Scale",
            author="by Digital Democracy 2030",
            source_root=en_root,
            order_file=en_root / "book_order.txt",
            label="English",
            edition_label="English edition",
            body_class="lang-en",
            part_labels=[
                ((0, 0), "Preface"),
                ((1, 3), "Part I: Concepts"),
                ((4, 11), "Part II: Case Studies"),
                ((12, 13), "Part III: Technology"),
                ((99, 99), "Appendix"),
            ],
        ),
    ]

    sites: dict[str, list[Chapter]] = {}
    for config in configs:
        canonical_map = reverse_map if config.code == "en" else {}
        sites[config.code] = build_chapters(repo_root, output_root, config, canonical_map)

    language_targets = build_language_targets(sites)
    english_config = next(config for config in configs if config.code == "en")

    generated: list[Path] = []
    root_index = output_root / "index.html"
    root_index.write_text(render_root_index(repo_root, output_root, configs), encoding="utf-8")
    generated.append(root_index)

    about_page = output_root / "about.html"
    about_page.write_text(render_about_page(english_config, "about.html"), encoding="utf-8")
    generated.append(about_page)

    feedback_page = output_root / "feedback.html"
    feedback_page.write_text(render_feedback_page(english_config, "feedback.html"), encoding="utf-8")
    generated.append(feedback_page)

    for config in configs:
        lang_dir = output_root / config.code
        lang_dir.mkdir(parents=True, exist_ok=True)

        about_path = lang_dir / "about.html"
        about_path.write_text(render_about_page(config, f"{config.code}/about.html"), encoding="utf-8")
        generated.append(about_path)

        feedback_path = lang_dir / "feedback.html"
        feedback_path.write_text(render_feedback_page(config, f"{config.code}/feedback.html"), encoding="utf-8")
        generated.append(feedback_path)

        index_path = lang_dir / "index.html"
        index_path.write_text(
            render_index(
                repo_root=repo_root,
                output_root=output_root,
                config=config,
                chapters=sites[config.code],
                configs=configs,
                language_targets=language_targets,
            ),
            encoding="utf-8",
        )
        generated.append(index_path)

        chapters = sites[config.code]
        for idx, chapter in enumerate(chapters):
            current_page_rel = f"{config.code}/{chapter.output_rel}"
            previous_href = (
                relative_href(current_page_rel, f"{config.code}/{chapters[idx - 1].output_rel}")
                if idx > 0
                else ""
            )
            next_href = (
                relative_href(current_page_rel, f"{config.code}/{chapters[idx + 1].output_rel}")
                if idx + 1 < len(chapters)
                else ""
            )
            page_path = output_root / config.code / chapter.output_rel
            page_path.parent.mkdir(parents=True, exist_ok=True)
            page_path.write_text(
                render_chapter_page(
                    current_page_rel=current_page_rel,
                    config=config,
                    configs=configs,
                    chapter=chapter,
                    all_chapters=chapters,
                    language_targets=language_targets,
                    previous_href=previous_href,
                    next_href=next_href,
                ),
                encoding="utf-8",
            )
            generated.append(page_path)

    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the multilingual web-book edition")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=default_book_source_dir(),
        help="Repository root (defaults to BOOK_SOURCE_DIR or ../broad-listening-book)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_site_output_dir(),
        help="Output directory for the generated static site",
    )
    args = parser.parse_args()

    generated = build_site(args.repo_root.resolve(), args.output_dir.resolve())
    print(f"Generated {len(generated)} files in {args.output_dir}")
    for path in generated[:20]:
        print(f"- {path}")
    if len(generated) > 20:
        print(f"... and {len(generated) - 20} more")


if __name__ == "__main__":
    main()
