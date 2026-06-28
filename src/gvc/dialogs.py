from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QVBoxLayout

from gvc.i18n import ui_text


def confirm_cancel_running(parent, tr) -> bool:
    choice = QMessageBox.question(
        parent,
        tr("operation_in_progress"),
        tr("operation_in_progress_text"),
    )
    return choice == QMessageBox.StandardButton.Yes


def show_warning(parent, title: str, message: str) -> None:
    QMessageBox.warning(parent, title, message)


def show_output_error(parent, tr, message: str) -> None:
    show_warning(parent, tr("open_output_folder"), message)


def show_open_output_failed(parent, tr) -> None:
    show_warning(parent, tr("open_output_folder"), tr("open_output_folder_error"))


def show_invalid_resolution(parent, tr, value: str) -> None:
    show_warning(
        parent,
        tr("invalid_resolution_title"),
        tr("invalid_resolution_text", value=value),
    )


def show_no_files(parent, tr) -> None:
    show_warning(parent, tr("no_files_title"), tr("no_files_text"))


def show_invalid_fps(parent, tr, message: str) -> None:
    show_warning(parent, tr("invalid_fps_title"), message)


def choose_batch_scope(parent, tr, *, selected_count: int, total_count: int) -> str | None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(tr("batch_scope_title"))
    box.setText(tr("batch_scope_text", selected=selected_count, total=total_count))
    selected_button = box.addButton(tr("batch_scope_selected"), QMessageBox.ButtonRole.AcceptRole)
    all_button = box.addButton(tr("batch_scope_all"), QMessageBox.ButtonRole.YesRole)
    box.addButton(tr("cancel"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(selected_button)
    box.exec()

    clicked = box.clickedButton()
    if clicked == selected_button:
        return "selected"
    if clicked == all_button:
        return "all"
    return None


def show_about(parent, tr, version: str) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(tr("about"))
    dialog.resize(520, 260)

    layout = QVBoxLayout(dialog)
    title = QLabel(tr("window_title"))
    body = QLabel(tr("about_text", version=version))
    body.setWordWrap(True)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=dialog)
    buttons.accepted.connect(dialog.accept)

    layout.addWidget(title)
    layout.addWidget(body, 1)
    layout.addWidget(buttons)

    dialog.exec()


def show_ffmpeg_not_found(language: str, message: str) -> None:
    title = ui_text(language, "ffmpeg_not_found")
    QMessageBox.critical(None, title, message)
