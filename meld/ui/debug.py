import logging

from gi.repository import Gio, Gtk

log = logging.getLogger("meld.ui.debug")


def install_ui_debug_hooks():
    log.info("Installing detailed Meld UI Activity Debug Hooks")

    # 1. Hook Gtk.Button clicks
    try:
        original_button_init = Gtk.Button.__init__
        def custom_button_init(self, *args, **kwargs):
            original_button_init(self, *args, **kwargs)
            def on_clicked(btn):
                label = btn.get_label()
                name = btn.get_name()
                tooltip = btn.get_tooltip_text()
                action_name = btn.get_action_name()
                desc = f"label='{label}'" if label else f"name='{name}'"
                if tooltip:
                    desc += f" tooltip='{tooltip}'"
                if action_name:
                    desc += f" action='{action_name}'"
                log.info(f"[UI Activity] Button Clicked: {btn.__class__.__name__} ({desc})")
            self.connect("clicked", on_clicked)
        Gtk.Button.__init__ = custom_button_init
        log.debug("Successfully hooked Gtk.Button clicks")
    except Exception as e:
        log.warning(f"Could not hook Gtk.Button clicks: {e}")

    # 2. Hook Gtk.Window presentation and lifecycle
    try:
        original_window_present = Gtk.Window.present
        def custom_window_present(self, *args, **kwargs):
            title = self.get_title()
            log.info(f"[UI Activity] Window Presented: {self.__class__.__name__} (title='{title}')")
            original_window_present(self, *args, **kwargs)
        Gtk.Window.present = custom_window_present

        original_window_init = Gtk.Window.__init__
        def custom_window_init(self, *args, **kwargs):
            original_window_init(self, *args, **kwargs)
            def on_close_request(win):
                log.info(f"[UI Activity] Window Close Requested: {win.__class__.__name__} (title='{win.get_title()}')")
                return False
            self.connect("close-request", on_close_request)
            def on_destroy(win):
                log.info(f"[UI Activity] Window Destroyed: {win.__class__.__name__}")
            self.connect("destroy", on_destroy)
        Gtk.Window.__init__ = custom_window_init
        log.debug("Successfully hooked Gtk.Window lifecycle")
    except Exception as e:
        log.warning(f"Could not hook Gtk.Window: {e}")

    # 3. Hook Gtk.Notebook page switching and management
    try:
        original_notebook_init = Gtk.Notebook.__init__
        def custom_notebook_init(self, *args, **kwargs):
            original_notebook_init(self, *args, **kwargs)
            def on_switch_page(notebook, page, page_num):
                page_class = page.__class__.__name__ if page else "Unknown"
                log.info(f"[UI Activity] Notebook Tab Switched: page_num={page_num} page_class={page_class}")
            self.connect("switch-page", on_switch_page)
        Gtk.Notebook.__init__ = custom_notebook_init

        original_append_page = Gtk.Notebook.append_page
        def custom_append_page(self, child, tab_label, *args, **kwargs):
            res = original_append_page(self, child, tab_label, *args, **kwargs)
            child_class = child.__class__.__name__ if child else "Unknown"
            log.info(f"[UI Activity] Notebook Tab Appended: child_class={child_class}")
            return res
        Gtk.Notebook.append_page = custom_append_page

        original_remove_page = Gtk.Notebook.remove_page
        def custom_remove_page(self, page_num, *args, **kwargs):
            page = self.get_nth_page(page_num)
            page_class = page.__class__.__name__ if page else "Unknown"
            log.info(f"[UI Activity] Notebook Tab Removed: page_num={page_num} page_class={page_class}")
            return original_remove_page(self, page_num, *args, **kwargs)
        Gtk.Notebook.remove_page = custom_remove_page
        log.debug("Successfully hooked Gtk.Notebook tabs")
    except Exception as e:
        log.warning(f"Could not hook Gtk.Notebook: {e}")

    # 4. Hook Gio.SimpleAction activations
    try:
        original_action_init = Gio.SimpleAction.__init__
        def custom_action_init(self, *args, **kwargs):
            original_action_init(self, *args, **kwargs)
            def on_activate(action, parameter):
                log.info(f"[UI Activity] SimpleAction Activated: name='{action.get_name()}' parameter={parameter}")
            self.connect("activate", on_activate)
        Gio.SimpleAction.__init__ = custom_action_init
        log.debug("Successfully hooked Gio.SimpleAction activations")
    except Exception as e:
        log.warning(f"Could not hook Gio.SimpleAction: {e}")

    # 5. Hook Gtk.TreeView row activations (e.g. file selection/clicks)
    try:
        original_treeview_init = Gtk.TreeView.__init__
        def custom_treeview_init(self, *args, **kwargs):
            original_treeview_init(self, *args, **kwargs)
            def on_row_activated(treeview, path, column):
                log.info(f"[UI Activity] TreeView Row Activated: path={path} column='{column.get_title() if column else 'None'}'")
            self.connect("row-activated", on_row_activated)
        Gtk.TreeView.__init__ = custom_treeview_init
        log.debug("Successfully hooked Gtk.TreeView row activations")
    except Exception as e:
        log.warning(f"Could not hook Gtk.TreeView: {e}")
