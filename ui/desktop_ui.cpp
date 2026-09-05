#include "desktop_ui.hpp"

#include <windows.h>
#include <commctrl.h>

#include <cstdint>
#include <string>
#include <vector>

#include "crypty/workflow.hpp"
#include "report.hpp"

namespace
{
    // -------------------------------------------------------------------------
    // IDs
    // -------------------------------------------------------------------------

    enum Id
    {
        TargetId = 101,
        InspectId,
        TabsId,
        RunId,
        ExportId,
        AuthId,
        TreeId,
        StateId,
        IntegrityId,
        FilesId,
        BytesId,
        RecoverableId,
        ProgressId,
        AuditId,
        PageTitleId,
        PageBodyId,
        PageMethodId,
        ExplorerTitleId,
        ExplorerSubtitleId,
        SnapshotTitleId,
        AuditTitleId
    };

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    crypty::Workflow workflow;

    HWND target = nullptr;
    HWND inspect = nullptr;
    HWND tree = nullptr;
    HWND tabs = nullptr;

    HWND state = nullptr;
    HWND integrity = nullptr;
    HWND files = nullptr;
    HWND bytes = nullptr;
    HWND recoverable = nullptr;
    HWND progress = nullptr;

    HWND audit = nullptr;
    HWND run = nullptr;
    HWND export_button = nullptr;
    HWND auth = nullptr;

    HWND page_title = nullptr;
    HWND page_body = nullptr;
    HWND page_method = nullptr;

    HWND explorer_title = nullptr;
    HWND explorer_subtitle = nullptr;
    HWND snapshot_title = nullptr;
    HWND audit_title = nullptr;

    HBRUSH background_brush = nullptr;
    HBRUSH panel_brush = nullptr;
    HBRUSH panel_alt_brush = nullptr;
    HBRUSH transparent_brush = nullptr;

    HFONT font_regular = nullptr;
    HFONT font_small = nullptr;
    HFONT font_title = nullptr;
    HFONT font_section = nullptr;
    HFONT font_mono = nullptr;

    // Create a font that fits comfortably inside a 40-pixel high box
HFONT hFont_normal = CreateFont(
    26,                        // nHeight: 26 pixels tall (fits great in a 40px box)
    0,                         // nWidth: 0 lets Windows choose the best width automatically
    0,                         // nEscapement: 0 for normal horizontal text
    0,                         // nOrientation: 0 for normal horizontal text
    FW_NORMAL,                 // fnWeight: FW_NORMAL (use FW_BOLD if you want it bold)
    FALSE,                     // fdwItalic: FALSE (not italic)
    FALSE,                     // fdwUnderline: FALSE (not underlined)
    FALSE,                     // fdwStrikeOut: FALSE (not struck out)
    DEFAULT_CHARSET,           // fdwCharSet: Default character set
    OUT_DEFAULT_PRECIS,        // fdwOutputPrecision: Default output precision
    CLIP_DEFAULT_PRECIS,       // fdwClipPrecision: Default clipping precision
    CLEARTYPE_QUALITY,         // fdwQuality: CLEARTYPE for smooth, anti-aliased text edges
    DEFAULT_PITCH | FF_DONTCARE,// fdwPitchAndFamily: Default pitch
    L"Arial"                   // lpszFace: The font family name
);

    // -------------------------------------------------------------------------
    // Theme
    // -------------------------------------------------------------------------

    const COLORREF Background = RGB(20, 25, 32);
    const COLORREF Panel      = RGB(32, 40, 50);
    const COLORREF PanelAlt   = RGB(27, 34, 43);

    const COLORREF Text       = RGB(235, 241, 245);
    const COLORREF Muted      = RGB(145, 158, 170);

    const COLORREF Accent     = RGB(104, 211, 194);
    const COLORREF Blue       = RGB(116, 166, 235);

    const COLORREF Border     = RGB(65, 78, 91);
    const COLORREF Hover      = RGB(55, 67, 80);

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    std::wstring wide(const std::string& value)
    {
        return {value.begin(), value.end()};
    }

    void place(HWND control, int x, int y, int w, int h)
    {
        if (control != nullptr)
            MoveWindow(control, x, y, w, h, TRUE);
    }

    void set(HWND control, const std::string& value)
    {
        if (control != nullptr)
        {
            const auto text = wide(value);
            SetWindowTextW(control, text.c_str());
        }
    }

    HWND label(
        HWND parent,
        const wchar_t* value,
        int x,
        int y,
        int w,
        int h,
        int id = 0)
    {
        return CreateWindowW(
            L"STATIC",
            value,
            WS_CHILD | WS_VISIBLE,
            x, y, w, h,
            parent,
            reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),
            nullptr,
            nullptr);
    }

    HWND button(HWND parent, const wchar_t* value, int id)
    {
        return CreateWindowW(
            L"BUTTON",
            value,
            WS_CHILD |
            WS_VISIBLE |
            WS_TABSTOP |
            BS_PUSHBUTTON |
            BS_OWNERDRAW,
            0, 0, 0, 0,
            parent,
            reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),
            nullptr,
            nullptr);
    }

    HFONT make_font(
        int size,
        int weight = FW_NORMAL,
        const wchar_t* face = L"Segoe UI")
    {
        return CreateFontW(
            -MulDiv(size, GetDeviceCaps(GetDC(nullptr), LOGPIXELSY), 72),
            0,
            0,
            0,
            weight,
            FALSE,
            FALSE,
            FALSE,
            DEFAULT_CHARSET,
            OUT_DEFAULT_PRECIS,
            CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY,
            DEFAULT_PITCH | FF_DONTCARE,
            face);
    }

    void apply_font(HWND control, HFONT font)
    {
        if (control != nullptr && font != nullptr)
            SendMessageW(control, WM_SETFONT,
                         reinterpret_cast<WPARAM>(font), TRUE);
    }

    void fill_rect(HDC dc, const RECT& r, COLORREF color)
    {
        HBRUSH brush = CreateSolidBrush(color);
        FillRect(dc, &r, brush);
        DeleteObject(brush);
    }

    void rounded_panel(
        HDC dc,
        int x,
        int y,
        int w,
        int h,
        COLORREF fill,
        COLORREF border,
        int radius = 16)
    {
        HBRUSH brush = CreateSolidBrush(fill);
        HPEN pen = CreatePen(PS_SOLID, 1, border);

        HGDIOBJ old_brush = SelectObject(dc, brush);
        HGDIOBJ old_pen = SelectObject(dc, pen);

        RoundRect(
            dc,
            x,
            y,
            x + w,
            y + h,
            radius,
            radius);

        SelectObject(dc, old_brush);
        SelectObject(dc, old_pen);

        DeleteObject(brush);
        DeleteObject(pen);
    }

    void draw_text(
        HDC dc,
        const wchar_t* text,
        const RECT& rect,
        COLORREF color,
        HFONT font,
        UINT format)
    {
        SetBkMode(dc, TRANSPARENT);
        SetTextColor(dc, color);

        HGDIOBJ old_font = nullptr;

        if (font != nullptr)
            old_font = SelectObject(dc, font);

        DrawTextW(
            dc,
            text,
            -1,
            const_cast<RECT*>(&rect),
            format);

        if (old_font != nullptr)
            SelectObject(dc, old_font);
    }

    // -------------------------------------------------------------------------
    // File explorer
    // -------------------------------------------------------------------------

    void add_tree(HTREEITEM parent, const crypty::FileEntry& entry)
    {
        auto name = wide(entry.name);

        TVINSERTSTRUCTW item{};
        item.hParent = parent;
        item.hInsertAfter = TVI_LAST;
        item.item.mask = TVIF_TEXT;
        item.item.pszText = const_cast<wchar_t*>(name.c_str());

        const HTREEITEM node = TreeView_InsertItem(tree, &item);

        for (const auto& child : entry.children)
            add_tree(node, child);
    }

    void refresh_tree()
    {
        if (tree == nullptr)
            return;

        TreeView_DeleteAllItems(tree);

        for (const auto& entry : workflow.snapshot().files)
            add_tree(TVI_ROOT, entry);
    }

    // -------------------------------------------------------------------------
    // Audit
    // -------------------------------------------------------------------------

    void refresh_audit()
    {
        if (audit == nullptr)
            return;

        SendMessageW(audit, LB_RESETCONTENT, 0, 0);

        for (const auto& event : workflow.snapshot().audit)
        {
            const auto line =
                wide(event.code + "  " + event.message);

            SendMessageW(
                audit,
                LB_ADDSTRING,
                0,
                reinterpret_cast<LPARAM>(line.c_str()));
        }
    }

    // -------------------------------------------------------------------------
    // UI refresh
    // -------------------------------------------------------------------------

    void refresh()
    {
        const auto snapshot = workflow.snapshot();

        set(
            state,
            snapshot.state == crypty::State::Complete
                ? "Complete"
                : snapshot.state == crypty::State::Running
                    ? "Running"
                    : snapshot.state == crypty::State::Inspected
                        ? "Inspected"
                        : "Ready");

        set(integrity, snapshot.integrity);
        set(files, std::to_string(snapshot.evidence_items));
        set(bytes, std::to_string(snapshot.total_bytes) + " B");

        std::uintmax_t possible = 0;

        for (const auto& item : snapshot.files)
            possible += item.recoverable;

        set(recoverable, std::to_string(possible) + " B");

        if (progress != nullptr)
            SendMessageW(
                progress,
                PBM_SETPOS,
                snapshot.progress,
                0);

        refresh_audit();
    }

    void select_tab(int index)
    {
        const bool erasure = index == 0;

        workflow.select_operation(
            erasure
                ? crypty::Operation::Erasure
                : crypty::Operation::Recovery);

        SetWindowTextW(
            page_title,
            erasure ? L"ERASURE" : L"RECOVERY");

        SetWindowTextW(
            page_body,
            erasure
                ? L"Prepare a media-aware sanitization operation.\r\n"
                  L"This demo never changes device data.\r\n"
                  L"A future adapter will verify the device before execution."
                : L"Review content that may be recoverable.\r\n"
                  L"The source inventory is read-only.\r\n"
                  L"Carving and fragment reconstruction come later.");

        SetWindowTextW(
            page_method,
            erasure
                ? L"METHOD   /   Cryptographic erase + device verification"
                : L"METHOD   /   Filesystem metadata + signature carving");

        SetWindowTextW(
            run,
            erasure
                ? L"Preview erasure"
                : L"Preview recovery");

        refresh();
    }

    // -------------------------------------------------------------------------
    // Layout
    // -------------------------------------------------------------------------

    void layout(HWND window)
    {
        RECT r{};
        GetClientRect(window, &r);

        const int w = r.right;
        const int h = r.bottom;

        const int header = static_cast<int>(h * 0.20);
        const int left_width = static_cast<int>(w * 0.30);

        const int margin = 24;

        const int explorer_x = margin;
        const int explorer_y = header + 18;
        const int explorer_w = left_width - margin * 2;
        const int explorer_h = h - explorer_y - margin;

        const int main_x = left_width + 8;
        const int main_y = header + 18;
        const int main_w = w - main_x - margin;
        const int main_h = h - main_y - margin;

        // ---------------------------------------------------------------------
        // Header
        // ---------------------------------------------------------------------

        place(target, 220, header / 2 + 20, w - 220 - 170, 38);
        place(inspect, w - 140, header / 2 + 20, 110, 38);

        // ---------------------------------------------------------------------
        // Explorer
        // ---------------------------------------------------------------------

        place(
            explorer_title,
            explorer_x + 18,
            explorer_y + 18,
            explorer_w - 36,
            24);

        place(
            explorer_subtitle,
            explorer_x + 18,
            explorer_y + 44,
            explorer_w - 36,
            18);

        place(
            tree,
            explorer_x + 14,
            explorer_y + 76,
            explorer_w - 28,
            explorer_h - 90);

        // ---------------------------------------------------------------------
        // Main tabs
        // ---------------------------------------------------------------------

        place(
            tabs,
            main_x,
            main_y,
            main_w,
            44);

        const int content_x = main_x + 28;
        const int content_w = main_w - 56;

        // ---------------------------------------------------------------------
        // Operation page
        // ---------------------------------------------------------------------

        place(
            page_title,
            content_x,
            main_y + 72,
            content_w,
            34);

        place(
            page_body,
            content_x,
            main_y + 112,
            content_w,
            72);

        place(
            page_method,
            content_x,
            main_y + 194,
            content_w,
            30);

        place(
            run,
            content_x,
            main_y + 238,
            content_w,
            42);

        place(
            export_button,
            content_x,
            main_y + 290,
            content_w,
            38);

        place(
            auth,
            content_x,
            main_y + 338,
            content_w,
            32);

        place(
            progress,
            content_x,
            main_y + 386,
            content_w,
            10);

        // ---------------------------------------------------------------------
        // Snapshot
        // ---------------------------------------------------------------------

        place(
            snapshot_title,
            content_x,
            main_y + 414,
            content_w,
            22);

        place(state, content_x, main_y + 444, 145, 26);
        place(integrity, content_x + 158, main_y + 444, 150, 26);
        place(files, content_x + 323, main_y + 444, 120, 26);

        place(bytes, content_x, main_y + 478, 150, 26);
        place(recoverable, content_x + 158, main_y + 478, 180, 26);

        // ---------------------------------------------------------------------
        // Audit
        // ---------------------------------------------------------------------

        place(
            audit_title,
            content_x,
            main_y + 510,
            content_w,
            22);

        place(
            audit,
            content_x,
            main_y + 540,
            content_w,
            main_h - 558);
    }

    // -------------------------------------------------------------------------
    // Owner-drawn buttons
    // -------------------------------------------------------------------------

    LRESULT draw_button(const DRAWITEMSTRUCT* dis)
    {
        if (dis == nullptr)
            return FALSE;

        HDC dc = dis->hDC;
        RECT r = dis->rcItem;

        const bool pressed =
            (dis->itemState & ODS_SELECTED) != 0;

        const bool focused =
            (dis->itemState & ODS_FOCUS) != 0;

        const bool is_primary =
            dis->CtlID == InspectId ||
            dis->CtlID == RunId;

        COLORREF fill =
            is_primary
                ? (pressed ? RGB(72, 145, 137) : RGB(58, 112, 108))
                : (pressed ? Hover : PanelAlt);

        COLORREF outline =
            is_primary
                ? Accent
                : Border;

        HBRUSH brush = CreateSolidBrush(fill);
        HPEN pen = CreatePen(PS_SOLID, focused ? 2 : 1, outline);

        HGDIOBJ old_brush = SelectObject(dc, brush);
        HGDIOBJ old_pen = SelectObject(dc, pen);

        RoundRect(
            dc,
            r.left + 1,
            r.top + 1,
            r.right - 1,
            r.bottom - 1,
            10,
            10);

        SelectObject(dc, old_brush);
        SelectObject(dc, old_pen);

        DeleteObject(brush);
        DeleteObject(pen);

        wchar_t text[256]{};
        GetWindowTextW(dis->hwndItem, text, 256);

        RECT text_rect = r;
        draw_text(
            dc,
            text,
            text_rect,
            Text,
            font_regular,
            DT_CENTER | DT_VCENTER | DT_SINGLELINE);

        return TRUE;
    }

    // -------------------------------------------------------------------------
    // Window procedure
    // -------------------------------------------------------------------------

    LRESULT CALLBACK proc(
        HWND window,
        UINT message,
        WPARAM wParam,
        LPARAM lParam)
    {
        switch (message)
        {
            case WM_CREATE:
            {
                return 0;
            }

            case WM_SIZE:
            {
                layout(window);
                InvalidateRect(window, nullptr, FALSE);
                return 0;
            }

            case WM_PAINT:
            {
                PAINTSTRUCT ps{};
                HDC dc = BeginPaint(window, &ps);

                RECT r{};
                GetClientRect(window, &r);

                fill_rect(dc, r, Background);

                const int w = r.right;
                const int h = r.bottom;

                const int header =
                    static_cast<int>(h * 0.20);

                const int left_width =
                    static_cast<int>(w * 0.30);

                // Header
                rounded_panel(
                    dc,
                    18,
                    18,
                    w - 36,
                    header - 30,
                    Panel,
                    Border,
                    18);

                // Explorer glass panel
                rounded_panel(
                    dc,
                    18,
                    header + 18,
                    left_width - 28,
                    h - header - 36,
                    Panel,
                    Border,
                    18);

                // Main workspace glass panel
                rounded_panel(
                    dc,
                    left_width + 8,
                    header + 18,
                    w - left_width - 26,
                    h - header - 36,
                    Panel,
                    Border,
                    18);

                // Small accent line beneath the branding.
                RECT accent_rect{
                    42,
                    93,
                    138,
                    95
                };

                fill_rect(dc, accent_rect, Accent);

                EndPaint(window, &ps);
                return 0;
            }

            case WM_DRAWITEM:
            {
                const auto* dis = reinterpret_cast<const DRAWITEMSTRUCT*>(lParam);

                if (dis != nullptr && dis->CtlType == ODT_BUTTON)
                {
                    return draw_button(dis);
                }

                break;
            }

            case WM_COMMAND:
            {
                const int id = LOWORD(wParam);

                if (id == InspectId)
                {
                    wchar_t value[512]{};

                    GetWindowTextW(
                        target,
                        value,
                        static_cast<int>(std::size(value)));

                    const std::wstring target_value(value);

                    workflow.inspect_target(
                        std::string(
                            target_value.begin(),
                            target_value.end()));

                    refresh_tree();
                    refresh();

                    return 0;
                }

                if (id == RunId)
                {
                    workflow.start();

                    EnableWindow(run, FALSE);

                    SetTimer(
                        window,
                        1,
                        250,
                        nullptr);

                    refresh();

                    return 0;
                }

                if (id == ExportId)
                {
                    crypty::write_report(
                        workflow.snapshot(),
                        "crypty-case-0248.json");

                    refresh_audit();
                    return 0;
                }

                if (id == AuthId)
                {
                    refresh_audit();
                    return 0;
                }

                return 0;
            }

            case WM_NOTIFY:
            {
                const auto* header =
                    reinterpret_cast<LPNMHDR>(lParam);

                if (header != nullptr &&
                    header->idFrom == TabsId &&
                    header->code == TCN_SELCHANGE)
                {
                    select_tab(
                        TabCtrl_GetCurSel(tabs));
                }

                return 0;
            }

            case WM_TIMER:
            {
                if (wParam == 1)
                {
                    workflow.advance();
                    refresh();

                    if (workflow.snapshot().state ==
                        crypty::State::Complete)
                    {
                        KillTimer(window, 1);
                        EnableWindow(run, TRUE);
                    }
                }

                return 0;
            }

            case WM_CTLCOLORSTATIC:
            {
                HDC dc =
                    reinterpret_cast<HDC>(wParam);

                HWND control =
                    reinterpret_cast<HWND>(lParam);

                SetTextColor(dc, Text);
                SetBkMode(dc, TRANSPARENT);

                // Labels sit on top of the glass panel.
                // Transparent background keeps the panel visible.
                if (control == page_title ||
                    control == explorer_title ||
                    control == snapshot_title ||
                    control == audit_title)
                {
                    SetTextColor(dc, Text);
                }
                else if (control == page_method ||
                         control == explorer_subtitle)
                {
                    SetTextColor(dc, Muted);
                }
                else
                {
                    SetTextColor(dc, Text);
                }

                return reinterpret_cast<LRESULT>(
                    transparent_brush);
            }

            case WM_CTLCOLOREDIT:
            {
                HDC dc =
                    reinterpret_cast<HDC>(wParam);

                SetTextColor(dc, Text);
                SetBkColor(dc, PanelAlt);

                return reinterpret_cast<LRESULT>(
                    panel_alt_brush);
            }

            case WM_CTLCOLORLISTBOX:
            {
                HDC dc =
                    reinterpret_cast<HDC>(wParam);

                SetTextColor(dc, Text);
                SetBkColor(dc, PanelAlt);

                return reinterpret_cast<LRESULT>(
                    panel_alt_brush);
            }

            case WM_ERASEBKGND:
            {
                // WM_PAINT owns the background.
                return 1;
            }

            case WM_DESTROY:
            {
                if (background_brush != nullptr)
                    DeleteObject(background_brush);

                if (panel_brush != nullptr)
                    DeleteObject(panel_brush);

                if (panel_alt_brush != nullptr)
                    DeleteObject(panel_alt_brush);

                if (transparent_brush != nullptr)
                    DeleteObject(transparent_brush);

                if (font_regular != nullptr)
                    DeleteObject(font_regular);

                if (font_small != nullptr)
                    DeleteObject(font_small);

                if (font_title != nullptr)
                    DeleteObject(font_title);

                if (font_section != nullptr)
                    DeleteObject(font_section);

                if (font_mono != nullptr)
                    DeleteObject(font_mono);

                PostQuitMessage(0);
                return 0;
            }
        }

        return DefWindowProcW(
            window,
            message,
            wParam,
            lParam);
    }

    // -------------------------------------------------------------------------
    // Controls
    // -------------------------------------------------------------------------

    void controls(HWND window, HINSTANCE module)
    {
        // ---------------------------------------------------------------------
        // Header
        // ---------------------------------------------------------------------

        HWND brand =
            label(
                window,
                L"CRYPTY",
                42, 32,
                240, 38);

        apply_font(brand, font_title);

        HWND subtitle =
            label(
                window,
                L"SECURE DATA OPERATIONS  /  CASE-0248",
                42, 70,
                420, 20);

        apply_font(subtitle, font_small);

        HWND engine =
            label(
                window,
                L"LOCAL ENGINE  •  DEMO MODE",
                0, 0,
                240, 20);

        apply_font(engine, font_small);
        SetWindowPos(
            engine,
            HWND_TOP,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE);

        HWND target_label =
            label(
                window,
                L"TARGET VOLUME",
                42, 120,
                300, 40);

        apply_font(target_label, hFont_normal);

        // Editable combo = selector + manual volume entry.
        target =
            CreateWindowW(
                L"COMBOBOX",
                L".",
                WS_CHILD |
                WS_VISIBLE |
                WS_TABSTOP |
                WS_VSCROLL |
                CBS_DROPDOWN |
                CBS_AUTOHSCROLL,
                0, 0, 0, 0,
                window,
                reinterpret_cast<HMENU>(
                    static_cast<INT_PTR>(TargetId)),
                module,
                nullptr);

        SendMessageW(
            target,
            CB_ADDSTRING,
            0,
            reinterpret_cast<LPARAM>(L"."));

        SendMessageW(
            target,
            CB_ADDSTRING,
            0,
            reinterpret_cast<LPARAM>(L"C:\\"));

        SendMessageW(
            target,
            CB_ADDSTRING,
            0,
            reinterpret_cast<LPARAM>(L"D:\\"));

        SendMessageW(
            target,
            CB_ADDSTRING,
            0,
            reinterpret_cast<LPARAM>(L"E:\\"));

        SendMessageW(
            target,
            CB_SETCURSEL,
            0,
            0);

        apply_font(target, font_regular);

        inspect =
            button(
                window,
                L"Inspect",
                InspectId);

        // ---------------------------------------------------------------------
        // Explorer
        // ---------------------------------------------------------------------

        explorer_title =
            label(
                window,
                L"EVIDENCE EXPLORER",
                0, 0,
                260, 24,
                ExplorerTitleId);

        apply_font(explorer_title, font_section);

        explorer_subtitle =
            label(
                window,
                L"READ-ONLY SOURCE INVENTORY",
                0, 0,
                260, 18,
                ExplorerSubtitleId);

        apply_font(explorer_subtitle, font_small);

        tree =
            CreateWindowW(
                WC_TREEVIEWW,
                L"",
                WS_CHILD |
                WS_VISIBLE |
                WS_BORDER |
                TVS_HASLINES |
                TVS_LINESATROOT |
                TVS_HASBUTTONS |
                TVS_SHOWSELALWAYS,
                0, 0, 0, 0,
                window,
                reinterpret_cast<HMENU>(
                    static_cast<INT_PTR>(TreeId)),
                module,
                nullptr);

        apply_font(tree, font_regular);

        TreeView_SetBkColor(tree, PanelAlt);
        TreeView_SetTextColor(tree, Text);

        // ---------------------------------------------------------------------
        // Main workspace / tabs
        // ---------------------------------------------------------------------

        tabs =
            CreateWindowW(
                WC_TABCONTROLW,
                L"",
                WS_CHILD |
                WS_VISIBLE |
                WS_TABSTOP |
                TCS_FLATBUTTONS |
                TCS_FOCUSNEVER,
                0, 0, 0, 0,
                window,
                reinterpret_cast<HMENU>(
                    static_cast<INT_PTR>(TabsId)),
                module,
                nullptr);

        apply_font(tabs, font_regular);

        TCITEMW item{};
        item.mask = TCIF_TEXT;

        item.pszText =
            const_cast<wchar_t*>(L"Erasure");

        TabCtrl_InsertItem(
            tabs,
            0,
            &item);

        item.pszText =
            const_cast<wchar_t*>(L"Recovery");

        TabCtrl_InsertItem(
            tabs,
            1,
            &item);

        // ---------------------------------------------------------------------
        // Operation content
        // ---------------------------------------------------------------------

        page_title =
            label(
                window,
                L"ERASURE",
                0, 0,
                400, 34,
                PageTitleId);

        apply_font(page_title, font_title);

        page_body =
            label(
                window,
                L"Prepare a media-aware sanitization operation.\r\n"
                L"This demo never changes device data.\r\n"
                L"A future adapter will verify the device before execution.",
                0, 0,
                700, 72,
                PageBodyId);

        apply_font(page_body, font_regular);

        page_method =
            label(
                window,
                L"METHOD   /   Cryptographic erase + device verification",
                0, 0,
                700, 30,
                PageMethodId);

        apply_font(page_method, font_small);

        run =
            button(
                window,
                L"Preview erasure",
                RunId);

        export_button =
            button(
                window,
                L"Export report",
                ExportId);

        auth =
            button(
                window,
                L"Auth placeholder: skipped",
                AuthId);

        // ---------------------------------------------------------------------
        // Progress
        // ---------------------------------------------------------------------

        progress =
            CreateWindowW(
                PROGRESS_CLASSW,
                nullptr,
                WS_CHILD |
                WS_VISIBLE,
                0, 0, 0, 0,
                window,
                reinterpret_cast<HMENU>(
                    static_cast<INT_PTR>(ProgressId)),
                module,
                nullptr);

        SendMessageW(
            progress,
            PBM_SETRANGE,
            0,
            MAKELPARAM(0, 100));

        SendMessageW(
            progress,
            PBM_SETPOS,
            0,
            0);

        // ---------------------------------------------------------------------
        // Snapshot
        // ---------------------------------------------------------------------

        snapshot_title =
            label(
                window,
                L"STORAGE SNAPSHOT",
                0, 0,
                300, 22,
                SnapshotTitleId);

        apply_font(snapshot_title, font_section);

        state =
            label(
                window,
                L"READY",
                0, 0,
                145, 26,
                StateId);

        integrity =
            label(
                window,
                L"Pending",
                0, 0,
                150, 26,
                IntegrityId);

        files =
            label(
                window,
                L"0",
                0, 0,
                120, 26,
                FilesId);

        bytes =
            label(
                window,
                L"0 B",
                0, 0,
                150, 26,
                BytesId);

        recoverable =
            label(
                window,
                L"0 B",
                0, 0,
                180, 26,
                RecoverableId);

        apply_font(state, font_mono);
        apply_font(integrity, font_mono);
        apply_font(files, font_mono);
        apply_font(bytes, font_mono);
        apply_font(recoverable, font_mono);

        // ---------------------------------------------------------------------
        // Audit
        // ---------------------------------------------------------------------

        audit_title =
            label(
                window,
                L"AUDIT LOG",
                0, 0,
                300, 22,
                AuditTitleId);

        apply_font(audit_title, font_section);

        audit =
            CreateWindowW(
                L"LISTBOX",
                nullptr,
                WS_CHILD |
                WS_VISIBLE |
                WS_BORDER |
                LBS_NOINTEGRALHEIGHT |
                LBS_NODATA,
                0, 0, 0, 0,
                window,
                reinterpret_cast<HMENU>(
                    static_cast<INT_PTR>(AuditId)),
                module,
                nullptr);

        apply_font(audit, font_mono);

        // LBS_NODATA prevents the listbox from maintaining its own strings,
        // so remove that style and let the existing LB_ADDSTRING logic work.
        LONG_PTR style = GetWindowLongPtrW(audit, GWL_STYLE);
        style &= ~LBS_NODATA;
        SetWindowLongPtrW(audit, GWL_STYLE, style);
    }
}

// -----------------------------------------------------------------------------
// Entry point
// -----------------------------------------------------------------------------

int initialize_ui()
{
    INITCOMMONCONTROLSEX common_controls{
        sizeof(common_controls),
        ICC_TREEVIEW_CLASSES |
        ICC_TAB_CLASSES |
        ICC_PROGRESS_CLASS |
        ICC_STANDARD_CLASSES
    };

    InitCommonControlsEx(&common_controls);

    const HINSTANCE module =
        GetModuleHandleW(nullptr);

    // -------------------------------------------------------------------------
    // Brushes
    // -------------------------------------------------------------------------

    background_brush = CreateSolidBrush(Background);
    panel_brush = CreateSolidBrush(Panel);
    panel_alt_brush = CreateSolidBrush(PanelAlt);

    // Transparent static controls use the background brush. The actual
    // panel is already painted by WM_PAINT.
    transparent_brush = CreateSolidBrush(Panel);

    // -------------------------------------------------------------------------
    // Fonts
    // -------------------------------------------------------------------------

    font_regular = make_font(10, FW_NORMAL);
    font_small = make_font(9, FW_NORMAL);
    font_title = make_font(16, FW_SEMIBOLD);
    font_section = make_font(10, FW_SEMIBOLD);
    font_mono = make_font(9, FW_NORMAL, L"Consolas");

    // -------------------------------------------------------------------------
    // Window class
    // -------------------------------------------------------------------------

    WNDCLASSW klass{};

    klass.hInstance = module;
    klass.lpfnWndProc = proc;
    klass.lpszClassName = L"CryptyCrystalWorkspace";
    klass.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    klass.hbrBackground = background_brush;

    const ATOM registered =
        RegisterClassW(&klass);

    if (!registered &&
        GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
    {
        return 1;
    }

    // -------------------------------------------------------------------------
    // Window
    // -------------------------------------------------------------------------

    HWND window =
        CreateWindowExW(
            WS_EX_COMPOSITED,
            MAKEINTATOM(registered),
            L"Crypty | Evidence Workspace",
            WS_OVERLAPPEDWINDOW |
            WS_MAXIMIZE,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            1200,
            760,
            nullptr,
            nullptr,
            module,
            nullptr);

    if (!window)
        return 1;

    controls(window, module);

    ShowWindow(window, SW_MAXIMIZE);
    UpdateWindow(window);

    layout(window);
    refresh();

    // -------------------------------------------------------------------------
    // Message loop
    // -------------------------------------------------------------------------

    MSG message{};

    while (GetMessageW(
        &message,
        nullptr,
        0,
        0) > 0)
    {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }

    return 0;
}
