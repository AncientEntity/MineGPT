package ryan.ryanplugins;

import org.bukkit.Bukkit;
import org.bukkit.command.CommandExecutor;
import org.bukkit.plugin.java.JavaPlugin;


public final class MineGPT extends JavaPlugin {

    private int taskId;

    @Override
    public void onEnable() {
        // Plugin startup logic
        this.getCommand("gpt").setExecutor((CommandExecutor) new GPTCommand());
        getServer().getPluginManager().registerEvents(new BookSignListener(this), this);

        taskId = Bukkit.getScheduler().scheduleSyncRepeatingTask(this, new Runnable() {
            @Override
            public void run() {
                for(String command : GPTCommand.currentCommands){
                    if(command.equals("")) {continue;}

                    System.out.println("COMMAND: " + command);

                    Bukkit.dispatchCommand(Bukkit.getConsoleSender(), command);
                }
            }
        }, 0L, 1L); // 0 tick delay, 1 tick interval

    }

    @Override
    public void onDisable() {
        // Plugin shutdown logic
        Bukkit.getScheduler().cancelTask(taskId);
    }



}
