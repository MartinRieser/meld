import logging
from typing import Optional

from gi.repository import Gio, GObject, Gtk

from meld.conf import _

log = logging.getLogger(__name__)


class MeldFileButton(Gtk.Button):
    __gtype_name__ = "MeldFileButton"

    file: Optional[Gio.File] = GObject.Property(
        type=Gio.File,
        nick="Most recently selected file",
    )

    pane: int = GObject.Property(
        type=int,
        nick="Index of pane associated with this file selector",
        flags=(GObject.ParamFlags.READWRITE | GObject.ParamFlags.CONSTRUCT_ONLY),
    )

    action: Gtk.FileChooserAction = GObject.Property(
        type=Gtk.FileChooserAction,
        nick="File selector action",
        flags=(GObject.ParamFlags.READWRITE | GObject.ParamFlags.CONSTRUCT_ONLY),
        default=Gtk.FileChooserAction.OPEN,
    )

    local_only: bool = GObject.Property(
        type=bool,
        nick="Whether selected files should be limited to local file:// URIs",
        flags=(GObject.ParamFlags.READWRITE | GObject.ParamFlags.CONSTRUCT_ONLY),
        default=True,
    )

    dialog_label: str = GObject.Property(
        type=str,
        nick="Label for the file selector dialog",
        flags=(GObject.ParamFlags.READWRITE | GObject.ParamFlags.CONSTRUCT_ONLY),
    )

    @GObject.Signal("file-selected")
    def file_selected_signal(self, pane: int, file: Gio.File) -> None: ...

    icon_action_map = {
        Gtk.FileChooserAction.OPEN: "document-open-symbolic",
        Gtk.FileChooserAction.SELECT_FOLDER: "folder-open-symbolic",
    }

    def get_file(self) -> Optional[Gio.File]:
        return self.file

    def set_file(self, gfile: Optional[Gio.File]) -> None:
        self.file = gfile
        if gfile:
            self.set_label(gfile.get_basename())
        else:
            self.set_label(_("(None)"))

    def set_current_folder(self, path: str) -> None:
        # FileDialog handles initial folder via initial_file or doesn't support setting folder directly without a file.
        # We can store this as an attribute or use it if needed, or simply pass.
        pass

    def set_current_folder_file(self, parent: Gio.File) -> None:
        pass

    def do_realize(self) -> None:
        Gtk.Button.do_realize(self)

        image = Gtk.Image.new_from_icon_name(
            self.icon_action_map[self.action], Gtk.IconSize.BUTTON
        )
        self.set_image(image)
        if self.file:
            self.set_label(self.file.get_basename())
        else:
            self.set_label(_("(None)"))

    def do_clicked(self) -> None:
        dialog = Gtk.FileDialog.new()
        dialog.set_title(self.dialog_label or "Select Folder")

        is_folder = self.action == Gtk.FileChooserAction.SELECT_FOLDER

        if self.file:
            dialog.set_initial_file(self.file)

        def on_dialog_done(obj, result):
            try:
                if is_folder:
                    gfile = obj.select_folder_finish(result)
                else:
                    gfile = obj.open_finish(result)
                if gfile:
                    self.set_file(gfile)
                    self.emit("file-selected", self.pane, self.file)
            except Exception as e:
                log.error("File dialog failed: %s", e)

        parent_win = self.get_native()
        if is_folder:
            dialog.select_folder(parent_win, None, on_dialog_done)
        else:
            dialog.open(parent_win, None, on_dialog_done)

