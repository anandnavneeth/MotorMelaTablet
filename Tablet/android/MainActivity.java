package com.nohesi.handlinglab;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.net.Uri;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Small Android shell. All parameter definitions come from the connected game. */
public class MainActivity extends Activity {
    private WebView web;
    private EditText address;
    private String origin="http://127.0.0.1:18740";
    private TextView status;
    private String pairingPin="";
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);
        pairingPin=getIntent().getStringExtra("pairingPin");
        setRequestedOrientation(android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(Color.rgb(16,24,32));
        root.setFocusableInTouchMode(true);
        // Insets are physical window values. Do not hardcode the tablet's pixels.
        root.setOnApplyWindowInsetsListener((v,insets)->{
            v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;
        });
        LinearLayout bar=new LinearLayout(this);bar.setPadding(dp(10),dp(6),dp(10),dp(6));bar.setGravity(android.view.Gravity.CENTER_VERTICAL);
        address=new EditText(this);address.setSingleLine(true);address.setTextSize(14);address.setTextColor(Color.WHITE);
        address.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);
        address.setContentDescription("PC address. USB uses 127.0.0.1:18740");
        String host=pairingPin!=null&&pairingPin.matches("[0-9]{6}")?origin:getPreferences(0).getString("host",origin);
        address.setText(host);bar.addView(address,new LinearLayout.LayoutParams(0,dp(48),1));
        Button connect=new Button(this);connect.setText("Connect");bar.addView(connect,new LinearLayout.LayoutParams(dp(110),dp(48)));
        root.addView(bar);status=new TextView(this);status.setTextSize(12);status.setTextColor(Color.rgb(154,175,185));status.setPadding(dp(18),0,dp(18),dp(6));
        status.setText("USB: connect to PC · Wi-Fi: enter PC address and pair");root.addView(status);
        web=new WebView(this);web.setBackgroundColor(Color.rgb(16,24,32));web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(false);web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);
        web.getSettings().setBuiltInZoomControls(false);web.getSettings().setTextZoom(100);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                Uri target=request.getUrl(),allowed=Uri.parse(origin);
                return !target.getScheme().equals(allowed.getScheme())||!target.getHost().equals(allowed.getHost())||target.getPort()!=allowed.getPort();
            }
            @Override public void onPageFinished(WebView view,String url){
                status.setText("Handling Lab · changes stay on the connected PC");android.webkit.CookieManager.getInstance().flush();
                if(url.equals(origin+"/")&&pairingPin!=null&&pairingPin.matches("[0-9]{6}")){
                    String pin=pairingPin;pairingPin="";
                    view.evaluateJavascript("fetch('/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin:'"+pin+"'})}).then(r=>r.json()).then(r=>{if(r.ok)location.reload();})",null);
                }
            }
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame())status.setText("PC unavailable. Start Tablet Lab on the PC, then tap Connect.");}
        });
        root.addView(web,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);
        root.requestFocus();
        connect.setOnClickListener(v->connect());connect();
    }
    @Override protected void onNewIntent(android.content.Intent intent){super.onNewIntent(intent);setIntent(intent);pairingPin=intent.getStringExtra("pairingPin");if(pairingPin!=null&&pairingPin.matches("[0-9]{6}"))address.setText("http://127.0.0.1:18740");connect();}
    private void connect(){
        String value=address.getText().toString().trim();if(!value.startsWith("http://"))value="http://"+value;
        Uri parsed=Uri.parse(value);
        String host=parsed.getHost();
        // This is a local development controller, not an unrestricted web browser.
        if(host==null||!(host.equals("localhost")||host.equals("127.0.0.1")||host.startsWith("192.168.")||host.startsWith("10.")||host.matches("172\\.(1[6-9]|2[0-9]|3[01])\\..*"))){status.setText("Enter the PC's private network IP address or 127.0.0.1 for USB.");return;}
        origin="http://"+host+":"+(parsed.getPort()<0?18740:parsed.getPort());
        address.setText(origin);getPreferences(0).edit().putString("host",origin).apply();web.loadUrl(origin+"/");
    }
    @Override public void onBackPressed(){if(web.canGoBack())web.goBack();else super.onBackPressed();}
    @Override protected void onDestroy(){web.destroy();super.onDestroy();}
}
