/*
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
*/

#define _CRT_SECURE_NO_WARNINGS

#include <windows.h>
#include <windowsX.h>
#include "main.h"
#include <vector>

#include <Shellapi.h>
#include <Shlwapi.h>

#define TRAYICONID	1
#define SWM_TRAYMSG	WM_APP

#pragma comment(lib,"Shell32.lib")
#pragma comment(lib,"User32.lib")


int WINDOW_TYPE_NORMAL=0;
int WINDOW_TYPE_NORMAL_NOT_RESIZABLE=1;
int WINDOW_TYPE_DIALOG=100;
int WINDOW_TYPE_POPUP=200;
int WINDOW_TYPE_TOOL=300;

CallbackTypeRepaint g_callbackRepaint;
CallbackTypeKeyboard g_callbackKeyboard;
CallbackTypeMouse g_callbackMouse;
CallbackTypeTimer g_callbackTimer;
CallbackTypeWindow g_callbackWindow;

char* className = "DWAWindowClass";
int classNameCnt=0;

HWND hwndTimer=NULL;


struct DWAWindow { 
	int id;
	HWND hwnd;
	HDC hdc;
	COLORREF penColor;
	NOTIFYICONDATAW notifyicon;
	HFONT hFont;
	int penWidth;
};

std::vector<DWAWindow*> windowList; 


DWAWindow* addWindow(int id,HWND hwnd){
	DWAWindow* ww = new DWAWindow();
	ww->id=id;
	ww->hwnd=hwnd;
	ww->penColor=RGB(0, 0, 0);
	ww->penWidth=1;
	ww->hFont=CreateFont(0,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_OUTLINE_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY, VARIABLE_PITCH,TEXT("Arial"));
	windowList.push_back(ww);
	return ww;
}

void removeWindowByHandle(HWND hwnd){
	for (unsigned int i=0;i<=windowList.size()-1;i++){
		if (windowList.at(i)->hwnd==hwnd){
			DWAWindow* dwa = windowList.at(i);
			windowList.erase(windowList.begin()+i);
			delete dwa;
			break;
		}
	}
}

DWAWindow* getWindowByHandle(HWND hwnd){
	if (windowList.size()==0){
		return NULL;
	}
	for (unsigned int i=0;i<=windowList.size()-1;i++){
		if (windowList.at(i)->hwnd==hwnd){
			return windowList.at(i);
		}
	}
	return NULL;
}

DWAWindow* getWindowByID(int id){
	if (windowList.size()==0){
		return NULL;
	}
	for (unsigned int i=0;i<=windowList.size()-1;i++){
		if (windowList.at(i)->id==id){
			return windowList.at(i);
		}
	}
	return NULL;
}

ULONGLONG getDllVersion(LPCTSTR lpszDllName)
{
    ULONGLONG ullVersion = 0;
	HINSTANCE hinstDll;
    hinstDll = LoadLibrary(lpszDllName);
    if(hinstDll)
    {
        DLLGETVERSIONPROC pDllGetVersion;
        pDllGetVersion = (DLLGETVERSIONPROC)GetProcAddress(hinstDll, "DllGetVersion");
        if(pDllGetVersion)
        {
            DLLVERSIONINFO dvi;
            HRESULT hr;
            ZeroMemory(&dvi, sizeof(dvi));
            dvi.cbSize = sizeof(dvi);
            hr = (*pDllGetVersion)(&dvi);
            if(SUCCEEDED(hr))
				ullVersion = MAKEDLLVERULL(dvi.dwMajorVersion, dvi.dwMinorVersion,0,0);
        }
        FreeLibrary(hinstDll);
    }
    return ullVersion;
}


__declspec(dllexport) void setCallbackRepaint(CallbackTypeRepaint callback){
	g_callbackRepaint = callback;
}

__declspec(dllexport) void setCallbackKeyboard(CallbackTypeKeyboard callback){
	g_callbackKeyboard = callback;
}

__declspec(dllexport) void setCallbackMouse(CallbackTypeMouse callback){
	g_callbackMouse = callback;
}

__declspec(dllexport) void setCallbackTimer(CallbackTypeTimer callback){
	g_callbackTimer=callback;
}

__declspec(dllexport) void setCallbackWindow(CallbackTypeWindow callback){
	g_callbackWindow=callback;
}

void fireCallBackRepaint(int id, int x,int y,int w, int h){
	if(g_callbackRepaint)
		g_callbackRepaint(id, x, y, w, h);
}

void fireCallBackKeyboard(int id, wchar_t* type, wchar_t* c){
	if(g_callbackKeyboard)
		g_callbackKeyboard(id, type, c, (bool)(GetKeyState(VK_SHIFT) & 0x8000),(bool)(GetKeyState(VK_CONTROL) & 0x8000),false,false);
}

void fireCallBackMouse(int id, wchar_t* type, int x, int y, int button){
	if(g_callbackMouse)
		g_callbackMouse(id, type, x, y, button);
}

bool fireCallBackWindow(int id, wchar_t* type){
	if(g_callbackWindow)
		return g_callbackWindow(id,type);
	return true;
}

void fireCallBackTimer(){
	if(g_callbackTimer)
		g_callbackTimer();
}

LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam){
	DWAWindow* dwawin=getWindowByHandle(hwnd);
	int xPos = 0;
	int yPos = 0;
	int button = 0;
	switch(msg){
		case SWM_TRAYMSG:
			if (dwawin==NULL){
				break;
			}
			switch(lParam){
				case WM_LBUTTONUP:
					fireCallBackWindow(dwawin->id,L"NOTIFYICON_ACTIVATE");
					break;
				case WM_LBUTTONDBLCLK:
					fireCallBackWindow(dwawin->id,L"NOTIFYICON_ACTIVATE");
					break;
				case WM_RBUTTONDOWN:
				case WM_CONTEXTMENU:
					fireCallBackWindow(dwawin->id,L"NOTIFYICON_CONTEXTMENU");
					return 1;
				}
			return 1;
        case WM_CLOSE:
			if (dwawin==NULL){
				break;
			}
			if (fireCallBackWindow(dwawin->id,L"ONCLOSE")){
				destroyWindow(dwawin->id);
			}
        break;
		case WM_PAINT:
			if (dwawin==NULL){
				break;
			}
			PAINTSTRUCT ps;
			dwawin->hdc = BeginPaint(dwawin->hwnd, &ps);
			SetBkMode(dwawin->hdc, TRANSPARENT);
			SelectObject(dwawin->hdc,dwawin->hFont);
			try{
				fireCallBackRepaint(dwawin->id,ps.rcPaint.left,ps.rcPaint.top,ps.rcPaint.right-ps.rcPaint.left,ps.rcPaint.bottom-ps.rcPaint.top);
			}catch(...){
			}
			EndPaint(dwawin->hwnd, &ps);
			dwawin->hdc=NULL;
	    break;
		case WM_TIMER:
			fireCallBackTimer();
		break;
	    case WM_ACTIVATE:
			if (dwawin==NULL){
				break;
			}
			if ((wParam==WA_ACTIVE) || (wParam==WA_CLICKACTIVE)){
				fireCallBackWindow(dwawin->id,L"ACTIVE");
			}else if (wParam==WA_INACTIVE){
				fireCallBackWindow(dwawin->id,L"INACTIVE");
			}
		break;
		case WM_ACTIVATEAPP:
			if (dwawin==NULL){
				break;
			}
			if (wParam==TRUE){
				fireCallBackWindow(dwawin->id,L"ACTIVE");
			}else{
				fireCallBackWindow(dwawin->id,L"INACTIVE");
			}
		break;
		case WM_KEYDOWN:
			if (dwawin==NULL){
				break;
			}
			if (wParam==VK_DELETE){
				fireCallBackKeyboard(dwawin->id,L"KEY",L"DELETE");
			}else if (wParam==VK_LEFT){
				fireCallBackKeyboard(dwawin->id,L"KEY",L"LEFT");
			}else if (wParam==VK_RIGHT){
				fireCallBackKeyboard(dwawin->id,L"KEY",L"RIGHT");
			}else if (wParam==VK_HOME){
				fireCallBackKeyboard(dwawin->id,L"KEY",L"HOME");
			}else if (wParam==VK_END){
				fireCallBackKeyboard(dwawin->id,L"KEY",L"END");
			}else if (wParam==VK_TAB){
				fireCallBackKeyboard(dwawin->id,L"KEY",L"TAB");
			}
		break;
		case WM_SYSCHAR:
			if (dwawin==NULL){
				break;
			}
			fireCallBackKeyboard(dwawin->id,L"CHAR",(wchar_t*)&wParam);
		break;
		case WM_CHAR:
			if (dwawin==NULL){
				break;
			}
			if (wParam==VK_ESCAPE){
				fireCallBackKeyboard(dwawin->id,L"KEY",L"ESCAPE");
			}else if (wParam==VK_RETURN){
				fireCallBackKeyboard(dwawin->id,L"KEY",L"RETURN");
			}else if (wParam==VK_BACK){
				fireCallBackKeyboard(dwawin->id,L"KEY",L"BACKSPACE");
			}else  if (wParam==24){ //CUT
				fireCallBackKeyboard(dwawin->id,L"COMMAND",L"CUT");
			}else  if (wParam==3){ //COPY
				fireCallBackKeyboard(dwawin->id,L"COMMAND",L"COPY");
			}else  if (wParam==22){ //PASTE
				fireCallBackKeyboard(dwawin->id,L"COMMAND",L"PASTE");
			}else  if (wParam>=32){
				fireCallBackKeyboard(dwawin->id,L"CHAR",(wchar_t*)&wParam);
			}
		break;
		case WM_MOUSEMOVE:
			if (dwawin==NULL){
				break;
			}
			xPos = GET_X_LPARAM(lParam); 
			yPos = GET_Y_LPARAM(lParam);
			button=0;
			if (wParam & MK_LBUTTON){
				button=1;
			}else if (wParam & MK_RBUTTON){
				button=2;
			}
			fireCallBackMouse(dwawin->id,L"MOVE",xPos,yPos,button);
		break;
		case WM_LBUTTONDOWN:
			if (dwawin==NULL){
				break;
			}
			xPos = GET_X_LPARAM(lParam); 
			yPos = GET_Y_LPARAM(lParam);
			fireCallBackMouse(dwawin->id,L"BUTTON_DOWN",xPos,yPos,1);
		break;
		case WM_LBUTTONUP:
			if (dwawin==NULL){
				break;
			}
			xPos = GET_X_LPARAM(lParam); 
			yPos = GET_Y_LPARAM(lParam);
			fireCallBackMouse(dwawin->id,L"BUTTON_UP",xPos,yPos,1);
		break;
		case WM_RBUTTONDOWN:
			if (dwawin==NULL){
				break;
			}
			xPos = GET_X_LPARAM(lParam); 
			yPos = GET_Y_LPARAM(lParam);
			fireCallBackMouse(dwawin->id,L"BUTTON_DOWN",xPos,yPos,2);
		break;
        case WM_RBUTTONUP:
			if (dwawin==NULL){
				break;
			}
			xPos = GET_X_LPARAM(lParam); 
			yPos = GET_Y_LPARAM(lParam);
			fireCallBackMouse(dwawin->id,L"BUTTON_UP",xPos,yPos,2);
		break;
		case WM_DESTROY:
			if (windowList.size()==0){
				PostQuitMessage(0);
			}
        break;
        default:
            return DefWindowProc(hwnd, msg, wParam, lParam);
    }
    return 0;
}

__declspec(dllexport) void destroyNotifyIcon(int id){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		if (dwawin->notifyicon.uFlags!=0){
			dwawin->notifyicon.uFlags = 0;
			Shell_NotifyIconW(NIM_DELETE,&dwawin->notifyicon);
		}
	}
}

__declspec(dllexport) void updateNotifyIcon(int id,wchar_t* iconPath,wchar_t* toolTip){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		if (dwawin->notifyicon.uFlags!=0){
			HINSTANCE hInstance = GetModuleHandle(NULL);
			dwawin->notifyicon.hIcon = (HICON)LoadImageW(hInstance, iconPath, IMAGE_ICON,0,0,LR_LOADFROMFILE | LR_DEFAULTSIZE);
			wcscpy(dwawin->notifyicon.szTip,toolTip);
			Shell_NotifyIconW(NIM_MODIFY,&dwawin->notifyicon);
			if(dwawin->notifyicon.hIcon && DestroyIcon(dwawin->notifyicon.hIcon))
				dwawin->notifyicon.hIcon = NULL;
		}
	}
}

__declspec(dllexport) void createNotifyIcon(int id,wchar_t* iconPath,wchar_t* toolTip){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		if (dwawin->notifyicon.uFlags==0){
			ZeroMemory(&dwawin->notifyicon,sizeof(NOTIFYICONDATA));
			ULONGLONG ullVersion = getDllVersion("Shell32.dll");
			if(ullVersion >= MAKEDLLVERULL(6,0,6,0))
				dwawin->notifyicon.cbSize = sizeof(NOTIFYICONDATA);
			else if(ullVersion >= MAKEDLLVERULL(6,0,0,0))
				dwawin->notifyicon.cbSize = NOTIFYICONDATA_V3_SIZE;
			else if(ullVersion >= MAKEDLLVERULL(5,0,0,0))
				dwawin->notifyicon.cbSize = NOTIFYICONDATA_V2_SIZE;
			else
				dwawin->notifyicon.cbSize = NOTIFYICONDATA_V1_SIZE;
			dwawin->notifyicon.uID = TRAYICONID;
			dwawin->notifyicon.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
			dwawin->notifyicon.hWnd = dwawin->hwnd;
			dwawin->notifyicon.uCallbackMessage = SWM_TRAYMSG;
			updateNotifyIcon(id,iconPath,toolTip);
			HINSTANCE hInstance = GetModuleHandle(NULL);
			dwawin->notifyicon.hIcon = (HICON)LoadImageW(hInstance, iconPath, IMAGE_ICON,0,0,LR_LOADFROMFILE | LR_DEFAULTSIZE);
			wcscpy(dwawin->notifyicon.szTip,toolTip);
			Shell_NotifyIconW(NIM_ADD,&dwawin->notifyicon);
			if(dwawin->notifyicon.hIcon && DestroyIcon(dwawin->notifyicon.hIcon))
				dwawin->notifyicon.hIcon = NULL;
		}
	}
}

__declspec(dllexport) int newWindow(int tp, int x, int y, int w, int h, wchar_t* iconPath){
	WNDCLASSEX wc;
    
	HINSTANCE hInstance = GetModuleHandle(NULL);

	HICON hIcon = NULL;
	if (iconPath!=NULL){
		hIcon=(HICON)LoadImageW(hInstance, iconPath, IMAGE_ICON,0,0,LR_LOADFROMFILE | LR_DEFAULTSIZE);
	}

	classNameCnt++;
	char cn[64] = ""; 
	sprintf(cn, "%s%d",className, classNameCnt);

	wc.cbSize        = sizeof(WNDCLASSEX);
    wc.style         = 0;
    wc.lpfnWndProc   = WndProc;
    wc.cbClsExtra    = 0;
    wc.cbWndExtra    = 0;
    wc.hInstance     = hInstance;
    wc.hIcon         = hIcon;
    wc.hCursor       = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW+1);
    wc.lpszMenuName  = NULL;
    wc.lpszClassName = cn;
    wc.hIconSm       = hIcon;
	
	if(!RegisterClassEx(&wc)){
        return -1;
    }
	
	int dwStyle=WS_OVERLAPPEDWINDOW;
	int dwStyleEx=0;
	if (tp==WINDOW_TYPE_NORMAL_NOT_RESIZABLE){
		dwStyle=WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX;
	}else if (tp==WINDOW_TYPE_DIALOG){
		dwStyle=WS_CAPTION|WS_POPUPWINDOW;
	}else if (tp==WINDOW_TYPE_TOOL){
		dwStyle=WS_CAPTION|WS_POPUPWINDOW;
		dwStyleEx=WS_EX_TOOLWINDOW;
	}else if (tp==WINDOW_TYPE_POPUP){
		dwStyle=WS_POPUP;
		dwStyleEx=WS_EX_TOPMOST|WS_EX_TOOLWINDOW;
	}	

	HWND hwnd;
	hwnd = CreateWindowEx(dwStyleEx, cn, NULL, dwStyle,x, y, w, h, NULL, NULL, hInstance, NULL);

	if(hwnd == NULL) {
        return -1;
    }

	RECT winRC,clientRC;
    GetWindowRect(hwnd,&winRC); 
    GetClientRect(hwnd,&clientRC);
    int dx = w-(clientRC.right-clientRC.left); 
    int dy = h-(clientRC.bottom-clientRC.top); 
	int nx=x;
	int nw=w;
	if (dx>0){
		nw+=dx;
		nx+=(dx/2);
	}
	int ny=y;
	int nh=h;
	if (dy>0){
		nh+=dy;
		ny+=(dy/2);
	}
	SetWindowPos(hwnd, NULL, nx, ny, nw, nh, SWP_NOZORDER | SWP_NOMOVE | SWP_NOACTIVATE) ;
	addWindow(classNameCnt,hwnd);

	if (hwndTimer==NULL){
		hwndTimer=hwnd;
		SetTimer(hwndTimer,1,100,(TIMERPROC) NULL);
	}
	return classNameCnt;
}

__declspec(dllexport) void destroyWindow(int id){
	DWAWindow* dwawin=getWindowByID(id);
	char cn[64] = ""; 
	sprintf(cn, "%s%d",className, dwawin->id);
	if (hwndTimer==dwawin->hwnd){
		KillTimer(hwndTimer,1);
		hwndTimer=NULL;
	}
	destroyNotifyIcon(id);
	HWND hh=dwawin->hwnd;
	DeleteObject(dwawin->hFont);
	removeWindowByHandle(hh);
	DestroyWindow(hh);
	UnregisterClass(cn,GetModuleHandle(NULL));
	//Aggiunge nuovamente timer
	if ((hwndTimer==NULL) && (windowList.size()>0)){
		hwndTimer=windowList.at(0)->hwnd;
		SetTimer(hwndTimer,1,100,(TIMERPROC) NULL);		
	}
	if (windowList.size()==0){
		PostQuitMessage(0);
	}

}

__declspec(dllexport) void setClipboardText(wchar_t* str){
    if (OpenClipboard(NULL)){
        EmptyClipboard();
        HGLOBAL hClipboardData;
		size_t size = (wcslen(str)+1) * sizeof(wchar_t);
        hClipboardData = GlobalAlloc(NULL, size);
        wchar_t* pchData = (wchar_t*)GlobalLock(hClipboardData);
		memcpy(pchData, str, size);
        SetClipboardData(CF_UNICODETEXT, hClipboardData);
        GlobalUnlock(hClipboardData);
        CloseClipboard();
    }
}

__declspec(dllexport) wchar_t* getClipboardText(){
	if (OpenClipboard(NULL)){
		HANDLE clip = GetClipboardData(CF_UNICODETEXT);
		wchar_t * c;
		c = (wchar_t*)clip;
		CloseClipboard();
		return (wchar_t*)c;
	}
	return L"";
}

__declspec(dllexport) void getScreenSize(int* size){
	size[0] = GetSystemMetrics(SM_CXSCREEN);
	size[1] = GetSystemMetrics(SM_CYSCREEN);
}

__declspec(dllexport) void getMousePosition(int* pos){
	POINT pt;
	GetCursorPos(&pt);
	pos[0]=pt.x;
	pos[1]=pt.y;
}

__declspec(dllexport) void clipRectangle(int id, int x, int y, int w, int h){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		SelectClipRgn(dwawin->hdc, NULL); 
		HRGN hrgn = CreateRectRgn(x,y,x+w,y+h);
		SelectClipRgn(dwawin->hdc, hrgn); 
		DeleteObject(hrgn);
	}
}

__declspec(dllexport) void clearClipRectangle(int id){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		SelectClipRgn(dwawin->hdc, NULL); 
	}
}

__declspec(dllexport) void penColor(int id, int r, int g, int b){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		dwawin->penColor = RGB(r, g, b);
	}
}

__declspec(dllexport) void penWidth(int id, int w){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		dwawin->penWidth=w;
	}
}

__declspec(dllexport) void drawLine(int id, int x1, int y1, int x2,int y2){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		HPEN hPenOld;
		HPEN hLinePen;
		hLinePen = CreatePen(PS_SOLID, dwawin->penWidth, dwawin->penColor);
		hPenOld = (HPEN)SelectObject(dwawin->hdc, hLinePen);

		MoveToEx(dwawin->hdc, x1, y1, NULL);
		LineTo(dwawin->hdc, x2, y2);

		SelectObject(dwawin->hdc, hPenOld);
		DeleteObject(hLinePen);
	}
}

__declspec(dllexport) void drawEllipse(int id, int x, int y, int w,int h){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		HPEN hLinePen = CreatePen(PS_SOLID, dwawin->penWidth, dwawin->penColor);
		HPEN hPenOld = (HPEN)SelectObject(dwawin->hdc, hLinePen);
		SetDCBrushColor(dwawin->hdc, dwawin->penColor);
		HGDIOBJ hbr = GetStockObject(NULL_BRUSH);
		HBRUSH hbrOld = (HBRUSH)SelectObject(dwawin->hdc, hbr);
		Ellipse(dwawin->hdc,x, y, x+w, y+h);
		SelectObject(dwawin->hdc, hbrOld);
		SelectObject(dwawin->hdc, hPenOld);
		DeleteObject(hbr);
		DeleteObject(hLinePen);
	}
}

__declspec(dllexport) void fillEllipse(int id, int x, int y, int w,int h){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		HPEN hLinePen = CreatePen(PS_SOLID, dwawin->penWidth, dwawin->penColor);
		HPEN hPenOld = (HPEN)SelectObject(dwawin->hdc, hLinePen);
		SetDCBrushColor(dwawin->hdc, dwawin->penColor);
		HGDIOBJ hbr = GetStockObject(DC_BRUSH);
		HBRUSH hbrOld = (HBRUSH)SelectObject(dwawin->hdc, hbr);
		Ellipse(dwawin->hdc,x, y, x+w, y+h);
		SelectObject(dwawin->hdc, hbrOld);
		SelectObject(dwawin->hdc, hPenOld);
		DeleteObject(hbr);
		DeleteObject(hLinePen);
	}
}

__declspec(dllexport) void drawText(int id, wchar_t* str, int x, int y){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		SetTextColor(dwawin->hdc,dwawin->penColor);
		RECT rec;
		rec.left=x;
		rec.top=y;
		rec.right=0;
		rec.bottom=0;	
		DrawTextExW(dwawin->hdc,str,-1,&rec,DT_LEFT | DT_NOCLIP,NULL);
	}
}

__declspec(dllexport) void fillRectangle(int id, int x, int y, int w, int h){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		HBRUSH hbrBkgnd = CreateSolidBrush(dwawin->penColor); 
		RECT rec;
		rec.left=x;
		rec.top=y;
		rec.right=x+w;
		rec.bottom=y+h;
		FillRect(dwawin->hdc,&rec,hbrBkgnd);
		DeleteObject(hbrBkgnd);
	}
}

__declspec(dllexport) int getTextHeight(int id){
	DWAWindow* dwawin=getWindowByID(id);
	HWND hwnd=dwawin->hwnd;
	TEXTMETRIC lptm;
	HDC dc=NULL;
	if (dwawin->hdc==NULL){
		dc=GetDC(hwnd);
		SelectObject(dc,dwawin->hFont);
	}else{
		dc=dwawin->hdc;
	}
	GetTextMetrics(dc,&lptm);
	return lptm.tmHeight;
}

__declspec(dllexport) int getTextWidth(int id,wchar_t* str){
	DWAWindow* dwawin=getWindowByID(id);
	HWND hwnd=dwawin->hwnd;
	RECT rec;
	rec.left=0;
	rec.top=0;
	rec.right=100000;
	rec.bottom=100000;
	HDC dc=NULL;
	if (dwawin->hdc==NULL){
		dc=GetDC(hwnd);
		SelectObject(dc,dwawin->hFont);
	}else{
		dc=dwawin->hdc;
	}
	if (DrawTextExW(dc,str,-1,&rec,DT_LEFT | DT_NOCLIP | DT_CALCRECT,NULL)==0){
		return 0;
	}
	return rec.right-rec.left;
}

__declspec(dllexport) void repaint(int id, int x, int y, int w,int h){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		RECT rec;
		rec.left=x;
		rec.top=y;
		rec.right=x+w;
		rec.bottom=y+h;
		HWND hwnd=dwawin->hwnd;
		InvalidateRect(hwnd,&rec,FALSE);
	}
}

__declspec(dllexport) void show(int id,int md){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		ShowWindow(dwawin->hwnd,SW_SHOW);
		UpdateWindow(dwawin->hwnd);
	}
}

__declspec(dllexport) void toFront(int id){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		ShowWindow(dwawin->hwnd, SW_RESTORE);
		SetForegroundWindow(dwawin->hwnd);
		UpdateWindow(dwawin->hwnd);
	}
}

__declspec(dllexport) void hide(int id){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		ShowWindow(dwawin->hwnd,SW_HIDE);
		UpdateWindow(dwawin->hwnd);
	}
}

__declspec(dllexport) void setTitle(int id, wchar_t* title){
	DWAWindow* dwawin=getWindowByID(id);
	if (dwawin!=NULL){
		SetWindowTextW(dwawin->hwnd, title);
	}
}

__declspec(dllexport) void loop(){
	MSG Msg;
	while(GetMessage(&Msg, NULL, 0, 0) > 0) {
        TranslateMessage(&Msg);
        DispatchMessage(&Msg);
    }    
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance,LPSTR lpCmdLine, int nCmdShow){
	//"images\\logo.ico"
	int id=newWindow(WINDOW_TYPE_NORMAL_NOT_RESIZABLE,100,100, 400, 300,L"C:\\Users\\Esterni.limatola\\Projects\\dwservice\\dwagent\\images\\logo.ico");
	setTitle(id,L"Titolo");
	//showTrayIcon(id,L"C:\\Users\\Esterni.limatola\\Projects\\dwservice\\dwagent\\images\\logo.ico",L"Prova Tooltip");
	if (id>=0){
		show(id,0);
		loop();
	}else{
		MessageBox(NULL, "Window Creation Failed!", "Error!",
            MB_ICONEXCLAMATION | MB_OK);
	}

	return 0;
}

__declspec(dllexport) BOOL isUserInAdminGroup() throw(){
    BOOL fInAdminGroup = FALSE;
    DWORD dwError = ERROR_SUCCESS;
    HANDLE hToken = NULL;
    HANDLE hTokenToCheck = NULL;
    DWORD cbSize = 0;
    OSVERSIONINFO osver = { sizeof(osver) };

    // Open the primary access token of the process for query and duplicate.
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY | TOKEN_DUPLICATE, 
        &hToken))
    {
        dwError = GetLastError();
        goto Cleanup;
    }

    // Determine whether system is running Windows Vista or later operating 
    // systems (major version >= 6) because they support linked tokens, but 
    // previous versions (major version < 6) do not.
    if (!GetVersionEx(&osver))
    {
        dwError = GetLastError();
        goto Cleanup;
    }

    if (osver.dwMajorVersion >= 6)
    {
        // Running Windows Vista or later (major version >= 6). 
        // Determine token type: limited, elevated, or default. 
        TOKEN_ELEVATION_TYPE elevType;
        if (!GetTokenInformation(hToken, TokenElevationType, &elevType, 
            sizeof(elevType), &cbSize))
        {
            dwError = GetLastError();
            goto Cleanup;
        }

        // If limited, get the linked elevated token for further check.
        if (TokenElevationTypeLimited == elevType)
        {
            if (!GetTokenInformation(hToken, TokenLinkedToken, &hTokenToCheck, 
                sizeof(hTokenToCheck), &cbSize))
            {
                dwError = GetLastError();
                goto Cleanup;
            }
        }
    }
    
    // CheckTokenMembership requires an impersonation token. If we just got a 
    // linked token, it already is an impersonation token.  If we did not get 
    // a linked token, duplicate the original into an impersonation token for 
    // CheckTokenMembership.
    if (!hTokenToCheck)
    {
        if (!DuplicateToken(hToken, SecurityIdentification, &hTokenToCheck))
        {
            dwError = GetLastError();
            goto Cleanup;
        }
    }

    // Create the SID corresponding to the Administrators group.
    BYTE adminSID[SECURITY_MAX_SID_SIZE];
    cbSize = sizeof(adminSID);
    if (!CreateWellKnownSid(WinBuiltinAdministratorsSid, NULL, &adminSID,  
        &cbSize))
    {
        dwError = GetLastError();
        goto Cleanup;
    }

    // Check if the token to be checked contains admin SID.
    // http://msdn.microsoft.com/en-us/library/aa379596(VS.85).aspx:
    // To determine whether a SID is enabled in a token, that is, whether it 
    // has the SE_GROUP_ENABLED attribute, call CheckTokenMembership.
    if (!CheckTokenMembership(hTokenToCheck, &adminSID, &fInAdminGroup)) 
    {
        dwError = GetLastError();
        goto Cleanup;
    }

Cleanup:
    // Centralized cleanup for all allocated resources.
    if (hToken)
    {
        CloseHandle(hToken);
        hToken = NULL;
    }
    if (hTokenToCheck)
    {
        CloseHandle(hTokenToCheck);
        hTokenToCheck = NULL;
    }

    // Throw the error if something failed in the function.
    if (ERROR_SUCCESS != dwError)
    {
        throw dwError;
    }

    return fInAdminGroup;
}


__declspec(dllexport) int isRunAsAdmin() throw(){
    BOOL fIsRunAsAdmin = FALSE;
    DWORD dwError = ERROR_SUCCESS;
    PSID pAdministratorsGroup = NULL;

    // Allocate and initialize a SID of the administrators group.
    SID_IDENTIFIER_AUTHORITY NtAuthority = SECURITY_NT_AUTHORITY;
    if (!AllocateAndInitializeSid(
        &NtAuthority, 
        2, 
        SECURITY_BUILTIN_DOMAIN_RID, 
        DOMAIN_ALIAS_RID_ADMINS, 
        0, 0, 0, 0, 0, 0, 
        &pAdministratorsGroup))
    {
        dwError = GetLastError();
        goto Cleanup;
    }

    // Determine whether the SID of administrators group is enabled in 
    // the primary access token of the process.
    if (!CheckTokenMembership(NULL, pAdministratorsGroup, &fIsRunAsAdmin))
    {
        dwError = GetLastError();
        goto Cleanup;
    }
Cleanup:
    // Centralized cleanup for all allocated resources.
    if (pAdministratorsGroup)
    {
        FreeSid(pAdministratorsGroup);
        pAdministratorsGroup = NULL;
    }
    // Throw the error if something failed in the function.
    if (ERROR_SUCCESS != dwError)
    {
        throw dwError;
    }
    return fIsRunAsAdmin;
}


__declspec(dllexport) BOOL isProcessElevated(){
    BOOL fIsElevated = FALSE;
    DWORD dwError = ERROR_SUCCESS;
    HANDLE hToken = NULL;
    // Open the primary access token of the process with TOKEN_QUERY.
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &hToken))
    {
        dwError = GetLastError();
        goto Cleanup;
    }
    // Retrieve token elevation information.
    TOKEN_ELEVATION elevation;
    DWORD dwSize;
    if (!GetTokenInformation(hToken, TokenElevation, &elevation, 
        sizeof(elevation), &dwSize))
    {
        // When the process is run on operating systems prior to Windows 
        // Vista, GetTokenInformation returns FALSE with the 
        // ERROR_INVALID_PARAMETER error code because TokenElevation is 
        // not supported on those operating systems.
        dwError = GetLastError();
        goto Cleanup;
    }
    fIsElevated = elevation.TokenIsElevated;
Cleanup:
    // Centralized cleanup for all allocated resources.
    if (hToken){
        CloseHandle(hToken);
        hToken = NULL;
    }

    // Throw the error if something failed in the function.
    if (ERROR_SUCCESS != dwError)    {
        throw dwError;
    }
    return fIsElevated;
}

__declspec(dllexport) BOOL isTaskRunning(int pid) {
	DWORD dwDesiredAccess = SYNCHRONIZE;
    BOOL  bInheritHandle  = FALSE;
	HANDLE hProcess = OpenProcess(dwDesiredAccess, bInheritHandle, pid);
    if (hProcess == NULL)
        return FALSE;
	DWORD ret = WaitForSingleObject(hProcess, 0);
	CloseHandle(hProcess);
	return ret == WAIT_TIMEOUT;
}