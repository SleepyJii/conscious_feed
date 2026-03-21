import { Button } from "@/components/ui/button"
import { useNavigate } from "react-router-dom"
import { buttonStyles } from "@/lib/global-styles"


interface NavbarProps {
  currentPath: string
}

export function Navbar({ currentPath }: NavbarProps) {
  const navigate = useNavigate()

  const navButtons = [
    { label: "Main", route: "/" },
    { label: "Config", route: "/config" },
    { label: "Dashboard", route: "/dashboard" },
  ]

  return (
    <div className="flex items-center justify-between gap-4 p-4 border-b">
      <div className="flex items-center gap-4">
        {navButtons.map((button) => (
          <Button
            key={button.route}
            className={buttonStyles}
            variant={currentPath === button.route ? "default" : "outline"}
            onClick={() => navigate(button.route)}
          >
            {button.label}
          </Button>
        ))}
        
      </div>
      <div className="flex items-center justify-center">
        <h1 className="font-medium">Conscious Fleet</h1>
      </div>
    </div>
  )
}
