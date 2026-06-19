# Meld Codebase TODO & FIXME Analysis

This document provides a comprehensive analysis and a structured task list of the `TODO` and `FIXME` comments found throughout the Meld codebase. The tasks have been grouped by architectural component to help organize refactoring and feature implementation.

---

## Component Checklist

- [ ] [1. Core UI, Window, & Tab Lifecycle](#1-core-ui-window--tab-lifecycle)
- [ ] [2. File Comparison & Editor Components (`filediff.py`)](#2-file-comparison--editor-components-filediffpy)
- [ ] [3. Directory Comparison Component (`dirdiff.py`)](#3-directory-comparison-component-dirdiffpy)
- [ ] [4. Version Control Integration (`vcview.py` & `meld/vc/`)](#4-version-control-integration-vcviewpy--meldvc)
- [ ] [5. Infrastructure, Build, & System Compatibility](#5-infrastructure-build--system-compatibility)

---

## 1. Core UI, Window, & Tab Lifecycle

This category covers the core window management, multiple tab switching, document state-machine definitions, and GObject template bindings.

### Task 1.1: GObject Initialization Multi-Inheritance Hack Cleanup
* **Location**: Multiple files:
  * [dirdiff.py:L609](file:///Users/martinrieser/Documents/antigravity/meld/meld/dirdiff.py#L609)
  * [filediff.py:L268](file:///Users/martinrieser/Documents/antigravity/meld/meld/filediff.py#L268)
  * [imagediff.py:L130](file:///Users/martinrieser/Documents/antigravity/meld/meld/imagediff.py#L130)
  * [vcview.py:L186](file:///Users/martinrieser/Documents/antigravity/meld/meld/vcview.py#L186)
* **Comment**: `# FIXME: This unimaginable hack exists because GObject (or GTK+?) doesn't actually correctly chain init calls...`
* **Developer Intent**: The GObject wrapper (`PyGObject`) does not always chain super-class `__init__` calls correctly when mixing standard Python classes and GObject wrappers. To make `@Gtk.Template` compile successfully, the UI widget class must inherit from `Gtk.Widget` (or subclasses) first. But the custom class also inherits from a mixin `MeldDoc`, whose initialization has to be called manually via `MeldDoc.__init__(self)`.
* **What is Unclear**: Whether modern versions of PyGObject/GTK4 have resolved this behavior, allowing pure cooperative multiple inheritance (`super().__init__()`) to work automatically.
* **Change Impact**: **Medium**. Refactoring this would improve code cleanliness and reduce repetitive boilerplate. However, if the underlying PyGObject issue is still present, removing the hack will break UI instantiation.

### Task 1.2: Expand Document Comparison States
* **Location**: [melddoc.py:L31](file:///Users/martinrieser/Documents/antigravity/meld/meld/melddoc.py#L31)
* **Comment**: `# TODO: Consider use-cases for states in gedit-enum-types.c`
* **Developer Intent**: `ComparisonState` currently defines only `Normal`, `Closing`, and `SavingError`. The author noted that `gedit` (a sister GNOME text editor) tracks richer states (e.g., loading, saving, externally modified, read-only, etc.) which allow the UI to react more robustly to external filesystem modifications or background saving statuses.
* **What is Unclear**: Which specific states from `gedit` are actually useful for Meld’s multi-pane diff views compared to a single-document editor.
* **Change Impact**: **Low/Medium**. Provides a foundation for implementing safer saving/loading indicators and preventing conflict issues when files are modified externally while saving.

### Task 1.3: Simplify Action State Variant Unpacking
* **Location**: [melddoc.py:L115](file:///Users/martinrieser/Documents/antigravity/meld/meld/melddoc.py#L115)
* **Comment**: `# TODO: Try to do GLib.Variant things here instead of in callers`
* **Developer Intent**: `GAction` state values are represented as strongly-typed `GLib.Variant` objects in Gio. Callers of `set_action_state` must manually wrap Python primitive types (like `bool`, `str`) into a `GLib.Variant` before passing them. The writer wants `set_action_state` to accept standard Python types and automatically convert them into variants.
* **What is Unclear**: How to cleanly detect the expected GVariant type signature of the action without caching or querying it from the action group.
* **Change Impact**: **Low**. Clean up and simplify the calling code throughout the application.

### Task 1.4: Rename Pseudo-Event Handlers to Avoid GTK Conflict
* **Location**: [melddoc.py:L165](file:///Users/martinrieser/Documents/antigravity/meld/meld/melddoc.py#L165)
* **Comment**: `# FIXME: Here and in subclasses, on_delete_event are not real GTK+ event handlers, and should be renamed.`
* **Developer Intent**: The method name `on_delete_event` sounds like it handles the window manager's `delete-event` signal. However, it uses a custom return type signature (`Gtk.ResponseType`) and is called manually by containers during tab teardowns. It should be renamed (e.g. `confirm_close` or `request_close`) to prevent confusion.
* **What is Unclear**: Finding all occurrences in subclasses and custom layouts to ensure no broken references occur.
* **Change Impact**: **Low**. Clean refactoring for developer sanity.

### Task 1.5: Decouple "Stop" Action from Window level
* **Location**: [meldwindow.py:L294](file:///Users/martinrieser/Documents/antigravity/meld/meld/meldwindow.py#L294)
* **Comment**: `# TODO: This is the only window-level action we have that still works on the "current" document like this.`
* **Developer Intent**: When a folder comparison is scanning, a "Stop" button appears. This action is routed by the main window invoking `self.current_doc().action_stop()`. Every other tab action is implemented via local actions bound to the document's self-contained `view_action_group`. The stop action should be moved to the tab's action group as well.
* **What is Unclear**: How the window header bar button should dynamically map its sensitivity and activation to this scoped action without manual delegation.
* **Change Impact**: **Low**. Greater architectural consistency for actions.

### Task 1.6: Modernize Template Subclassing Workaround
* **Location**: [ui/bufferselectors.py:L6](file:///Users/martinrieser/Documents/antigravity/meld/meld/ui/bufferselectors.py#L6)
* **Comment**: `# TODO: Current pygobject support for templates excludes subclassing of templated classes...`
* **Developer Intent**: `FilteredListSelector` cannot inherit from `Gtk.Grid` or carry a template because PyGObject fails to build subclasses that override a templated widget structure. As a result, the two subclasses (`EncodingSelector` and `SourceLangSelector`) have redundant template files and boilerplate definitions.
* **What is Unclear**: If modern PyGObject versions have solved this limitation or if we can change `FilteredListSelector` from inheritance to a composition model.
* **Change Impact**: **Medium**. Eliminates duplicate XML layout configurations and improves layout reusability.

---

## 2. File Comparison & Editor Components (`filediff.py`)

This component handles text rendering, editing, and inline differences.

### Task 2.1: Asynchronous and Context-Aware Line Breaks
* **Location**: [filediff.py:L2786](file:///Users/martinrieser/Documents/antigravity/meld/meld/filediff.py#L2786) and [meldbuffer.py:L78](file:///Users/martinrieser/Documents/antigravity/meld/meld/meldbuffer.py#L78)
* **Comment**: `# TODO: We need to insert a linebreak here, but there is no way to be certain what kind of linebreak to use.`
* **Developer Intent**: When inserting text or copying changes past the final line of a buffer, the code appends a newline character. Currently, it hardcodes `"\n"`. If the target file utilizes CRLF (`\r\n`) or CR (`\r`), this introduces inconsistent line endings into the document.
* **What is Unclear**: How to query the underlying buffer's primary line ending style (or GtkSourceView's format) at runtime to match it dynamically.
* **Change Impact**: **High** (Bug Prevention). Prevents silent corruptions where users save files with mixed line endings, which causes issues in version control (such as git showing the whole file as changed).

### Task 2.2: Fix Fading Highlights for Insert-Only Chunks
* **Location**: [filediff.py:L2798](file:///Users/martinrieser/Documents/antigravity/meld/meld/filediff.py#L2798) and [filediff.py:L2820](file:///Users/martinrieser/Documents/antigravity/meld/meld/filediff.py#L2820)
* **Comment**: `# FIXME: If the inserted chunk ends up being an insert chunk, then this animation is not visible...`
* **Developer Intent**: When code is copied from one pane to another, a fading color highlight animation plays. However, if the operation is a pure insertion (the destination has a range of length 0), the start and end text iterators are identical. Highlighting a zero-length range is invisible.
* **What is Unclear**: How to render an insertion highlight (e.g. drawing a thick horizontal line or animating the gutter indicator) since text marks cannot hold formatting on zero-length ranges.
* **Change Impact**: **Low/Medium**. Improves visual feedback, particularly in three-way diffs.

### Task 2.3: Define Specific Colors for Zero-Length / Delete Actions
* **Location**: [filediff.py:L2817](file:///Users/martinrieser/Documents/antigravity/meld/meld/filediff.py#L2817) and [filediff.py:L2836](file:///Users/martinrieser/Documents/antigravity/meld/meld/filediff.py#L2836)
* **Comment**: `# TODO: Need a more specific colour here; conflict is wrong`
* **Developer Intent**: When highlighting a deleted range or an empty/insert range after a merge action, the code defaults to the 'conflict' color. This is confusing because no conflict occurred. A dedicated highlight color (e.g., 'deleted' or 'empty-placeholder') should be defined.
* **What is Unclear**: Defining the palette names in Meld's CSS theme files without breaking custom GTK styles.
* **Change Impact**: **Low**. Better UI clarity during merge actions.

### Task 2.4: Delegate External Modification Checks to `GtkSource.FileSaver`
* **Location**: [filediff.py:L2424](file:///Users/martinrieser/Documents/antigravity/meld/meld/filediff.py#L2424)
* **Comment**: `# TODO: Think about removing this flag and above handling, and instead handling the GtkSource.FileSaverError.EXTERNALLY_MODIFIED error`
* **Developer Intent**: Meld checks file modification times manually before saving. The developer wants to remove this manual logic and instead configure `FileSaver` flags and catch the standard `EXTERNALLY_MODIFIED` exception in the async saving callback.
* **What is Unclear**: Ensuring that the error mapping handles all platform-specific discrepancies.
* **Change Impact**: **Medium**. Simplifies file saving logic and leverages native GtkSourceView capabilities.

### Task 2.5: UI Recovery Actions for Saving/Loading Errors
* **Location**: [filediff.py:L1880](file:///Users/martinrieser/Documents/antigravity/meld/meld/filediff.py#L1880) and [filediff.py:L2445](file:///Users/martinrieser/Documents/antigravity/meld/meld/filediff.py#L2445)
* **Comment**: `# TODO: Add custom reload-with-encoding handling...` and `# TODO: Handle recoverable error cases, like external modifications or invalid buffer characters.`
* **Developer Intent**: When a file fails to load or save due to encoding issues (e.g., character conversion failures) or concurrent edits, the app simply blocks the save and shows a warning dialog. The user should be offered options to force-save, overwrite, or reload using a different character encoding.
* **What is Unclear**: Designing a user-friendly popover or message bar layout to present options.
* **Change Impact**: **High**. Greatly improves data safety and recovery options.

### Task 2.6: Optimize File Comparison Warnings (Text Filter Masking)
* **Location**: [filediff.py:L2296](file:///Users/martinrieser/Documents/antigravity/meld/meld/filediff.py#L2296)
* **Comment**: `# TODO: Currently this only checks to see whether text filters are active... It would be better if we only showed this message if the filters *did* change the text...`
* **Developer Intent**: When text filters are active, Meld shows a warning saying "Files are identical but text filters are active and may be masking differences." This warning shows up even if the files would have been 100% identical without the filters. It should only be displayed if a raw comparison shows actual differences.
* **What is Unclear**: The best way to run a secondary background raw comparison without locking the UI thread.
* **Change Impact**: **Medium**. Eliminates unnecessary warning messages for the user.

### Task 2.7: Replace Named Indexing with Structured Objects (Myers Diff)
* **Location**: [filediff.py:L1155](file:///Users/martinrieser/Documents/antigravity/meld/meld/filediff.py#L1155)
* **Comment**: `# TODO: Move myers.DiffChunk to a more general place, update this to use it...`
* **Developer Intent**: Several functions return data tuples like `("Same", start0, end0, start1, end1)`. Accessing elements via numerical indices (e.g., `chunk[2]`) is error-prone. The code should use structured class objects like `DiffChunk` with clear named properties.
* **What is Unclear**: Refactoring the callers across all diff backends to use attributes without breaking compatibility.
* **Change Impact**: **Medium**. Code cleanup and bug prevention.

---

## 3. Directory Comparison Component (`dirdiff.py`)

This component lists and compares files and folder structures.

### Task 3.1: Differentiate Metadata Differences (DodgySame)
* **Location**: [dirdiff.py:L1988](file:///Users/martinrieser/Documents/antigravity/meld/meld/dirdiff.py#L1988) and [dirdiff.py:L1993](file:///Users/martinrieser/Documents/antigravity/meld/meld/dirdiff.py#L1993)
* **Comment**: `# TODO: Differentiate the DodgySame case`
* **Developer Intent**: "DodgySame" represents files that are byte-identical but differ in modification timestamps or permissions. Currently, they are treated as completely identical (`STATE_NORMAL`). Meld should highlight these files with a warning indicator or badge so the user is aware of metadata discrepancies.
* **What is Unclear**: Defining the visual style and emblem for dodgy-same states.
* **Change Impact**: **Medium**. Provides users with visibility into metadata-only mismatches.

### Task 3.2: Use Unsigned 64-Bit Integers for File Sizes
* **Location**: [dirdiff.py:L376](file:///Users/martinrieser/Documents/antigravity/meld/meld/dirdiff.py#L376)
* **Comment**: `# FIXME: size should be a GObject.TYPE_UINT64, but we use -1 as a flag`
* **Developer Intent**: The folder tree model maps file sizes to signed 64-bit integers (`GObject.TYPE_INT64`) because it uses `-1` to represent folders or files with errors. The tree store columns should use `UINT64` and handle missing states with a separate boolean column.
* **What is Unclear**: How this affects the tree-sorting algorithms and the default cell renderers.
* **Change Impact**: **Low/Medium**. Clean data types and safe handling of files larger than 9.22 Exabytes.

### Task 3.3: Optimize Read Block Size with `os.stat`
* **Location**: [dirdiff.py:L169](file:///Users/martinrieser/Documents/antigravity/meld/meld/dirdiff.py#L169)
* **Comment**: `# TODO: Get the block size from os.stat`
* **Developer Intent**: When reading file chunks to determine if they are identical, Meld reads in chunks of `4096` bytes. Querying `st_blksize` from `os.stat` would allow it to match the optimal disk sector size of the underlying filesystem.
* **What is Unclear**: Falling back gracefully on filesystems (or Windows platforms) where block size is not returned by `os.stat`.
* **Change Impact**: **Low**. Slight read performance improvement for large directory scans.

### Task 3.4: Auto-refresh Folder Comparison on Property Change
* **Location**: [dirdiff.py:L1865](file:///Users/martinrieser/Documents/antigravity/meld/meld/dirdiff.py#L1865)
* **Comment**: `# TODO: Updating the property won't have any effect on its own`
* **Developer Intent**: Changing the `status_filters` property does not automatically trigger a folder compare refresh because GObject property notifications are not linked. The setter should connect to `refresh()` directly.
* **What is Unclear**: Preventing double-scans if multiple filters change in quick succession.
* **Change Impact**: **Low**. Better internal code structure.

---

## 4. Version Control Integration (`vcview.py` & `meld/vc/`)

This component covers version control status checking and commit layouts.

### Task 4.1: Asynchronous VCS Push Checks
* **Location**: [vc/_vc.py:L267](file:///Users/martinrieser/Documents/antigravity/meld/meld/vc/_vc.py#L267)
* **Comment**: `# TODO: We can't do this; this shells out for each selection change...`
* **Developer Intent**: To determine whether the "Push" action button should be enabled, Meld checks if there are commits to push. However, executing this check shells out a synchronous VCS command (like `git status` or `darcs push --dry-run`) every time the user clicks a new row, causing lag. This check must run asynchronously.
* **What is Unclear**: How to cancel outstanding checks when selection changes quickly.
* **Change Impact**: **High**. Greatly improves UI responsiveness in VCS folders.

### Task 4.2: Support Partial Refresh in Flatten View Mode
* **Location**: [vcview.py:L876](file:///Users/martinrieser/Documents/antigravity/meld/meld/vcview.py#L876)
* **Comment**: `# XXX fixme` (inside `refresh_partial` else block)
* **Developer Intent**: If the user is in "Flat" view mode (where all folder levels are flattened into one list), doing a partial refresh (refreshing only the modified files) is not implemented. The code falls back to a complete refresh of the entire repository tree, which is slow and resets selection.
* **What is Unclear**: How to map the flattened tree iterator back to its actual relative parent directory to perform a targeted query.
* **Change Impact**: **Medium**. Faster updates in version control views when flattening is active.

### Task 4.3: Stage/Unstage and Revert Dialog Consolidation
* **Location**: [vcview.py:L796](file:///Users/martinrieser/Documents/antigravity/meld/meld/vcview.py#L796) and [vcview.py:L844](file:///Users/martinrieser/Documents/antigravity/meld/meld/vcview.py#L844)
* **Comment**: `# TODO: Improve and reuse this dialog for the non-VC delete action`
* **Developer Intent**: When removing files from version control, a custom warning dialog is built inline. This popup confirmation should be consolidated and reused for regular folder deletions.
* **What is Unclear**: Unifying options like "Trash" versus "Permanent Delete" into a single reusable component.
* **Change Impact**: **Low/Medium**. Consistent visual behavior for all file deletion actions.

### Task 4.4: Dynamic VCS Status and Commit Directory State Inheritance
* **Location**: [vc/_vc.py:L274](file:///Users/martinrieser/Documents/antigravity/meld/meld/vc/_vc.py#L274)
* **Comment**: `# TODO: We can't disable this for NORMAL, because folders don't inherit any state from their children...`
* **Developer Intent**: When committing directories, parent folders often appear with a `STATE_NORMAL` status even if their children are modified. The commit button must remain enabled for `STATE_NORMAL` directory entries, but this allows users to try committing folders that have no changes. Directories should inherit status states.
* **What is Unclear**: How to efficiently check recursive folder status without traversing the filesystem manually.
* **Change Impact**: **Medium**. Prevents users from running empty/failed commit actions.

---

## 5. Infrastructure, Build, & System Compatibility

This category covers cross-platform compatibility, Meson build scripts, and configurations.

### Task 5.1: Integrate `GKeyFile` for Recent Comparison Entries
* **Location**: [recent.py:L160](file:///Users/martinrieser/Documents/antigravity/meld/meld/recent.py#L160)
* **Comment**: `# TODO: Use GKeyFile instead, and return a Gio.File. This is why we're using ';' to join comparison paths.`
* **Developer Intent**: Recent comparison documents are saved in custom INI-like configurations using Python's `configparser`. This requires joining file paths with a semicolon. Using GLib's native `GKeyFile` API would handle list-type metadata cleanly and integrate directly with Gio.
* **What is Unclear**: Migrating legacy INI recent comparison files to GKeyFile format during upgrades.
* **Change Impact**: **Low/Medium**. Cleaner native config file reading.

### Task 5.2: Path Resolution on Windows (User Home Directory)
* **Location**: [recent.py:L117](file:///Users/martinrieser/Documents/antigravity/meld/meld/recent.py#L117)
* **Comment**: `# FIXME: What should we show on Windows?`
* **Developer Intent**: To display shortened paths, Meld replaces the user’s home directory path with `~`. On Windows, the home directory path is set up differently, and raw character slicing might result in odd paths (e.g. `~\Documents`). Windows-specific path resolution needs to be implemented.
* **What is Unclear**: Finding standard path shortening patterns that Windows users expect (e.g. `%USERPROFILE%` replacement).
* **Change Impact**: **Low**. Polishes Windows support.

### Task 5.3: Standardize Build Configuration with Meson `configure_file`
* **Location**: [meld/meson.build:L2](file:///Users/martinrieser/Documents/antigravity/meld/meld/meson.build#L2)
* **Comment**: `# TODO: Replace our existing conf.py hacks with configure_file().`
* **Developer Intent**: Meld historically used build-script replacements to inject values into `conf.py`. The build should rely exclusively on Meson's native `configure_file()` directive to produce configuration headers.
* **What is Unclear**: Checking if any remaining pre-Meson config hacks remain inside helper tools or the setup script.
* **Change Impact**: **Low**. Simplifies packaging and clean builds.
